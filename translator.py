import argparse
import importlib
import os
import sys
import re
import yaml
import json

from abc import ABC, abstractmethod

program = os.path.basename(sys.argv[0])
config_file = 'translation-config.yml'


class Driver:
    def main(self, args=sys.argv[1:], prog=program):
        options = self.parse_args(args, prog)
        config = self.load_config()
        Validator().validate(config)
        exporter = self.instantiate_exporter(config)
        importer = self.instantiate_importer(config)
        all_bundles = Bundler().gather(config)
        if options.generate:
            TranslationGenerator(options, all_bundles, exporter).generate_all()
        elif options.reconcile:
            Reconciliator(options, all_bundles).reconcile()

    def parse_args(self, args, prog):
        parser = argparse.ArgumentParser(
            prog=prog,
            description='Generator for candidate translation strings',
        )

        parser.add_argument('--output',
                            help='output type',
                            choices=("yaml", "json"),
                            default="yaml")

        mode = parser.add_mutually_exclusive_group(required=True)
        mode.add_argument('--generate',
                          help='generate snapshot file',
                          action='store_true', default=False)
        mode.add_argument('--reconcile',
                          help='sanitize locale files',
                          action='store_true', default=False)
        return parser.parse_args(args)

    def load_config(self):
        if os.path.exists(config_file):
            with open(config_file, 'r') as f:
                data = yaml.full_load(f)
        return data

    def instantiate_exporter(self, config):
        exporter_class_fqn = ConfigUtilities.get_value(config, ('io', 'out', 'generator'))
        exporter_class = self.get_class(exporter_class_fqn)
        return exporter_class(config)

    def instantiate_importer(self, config):
        importer_class_fqn = ConfigUtilities.get_value(config, ('io', 'in', 'importer'))
        importer_class = self.get_class(importer_class_fqn)
        return importer_class(config)

    def get_class(self, class_fqn):
        module_name = class_fqn[:class_fqn.rfind('.')]
        class_name = class_fqn[class_fqn.rfind('.') + 1:]
        io_module = importlib.import_module(module_name)
        return getattr(io_module, class_name)


class JsonProcessor(object):
    '''
        Processor that can convert json content in files to a python
        dictionary keyed with the file name
    '''
    files = []
    dict_representation = {}

    def __init__(self, files):
        self.files = set(files)
        self.parse_to_dict(files)

    def parse_to_dict(self, files):
        for file in files:
            with open(file) as f:
                dictdump = json.loads(f.read())
            self.dict_representation[file] = dictdump

    def get_as_dictionary(self):
        return self.dict_representation


class PropertiesProcessor(object):
    '''
        Processor that can convert a properties file to a python
        dictionary keyed with the file name
    '''
    files = []
    separator = '='
    comment_char = '#'
    dict_representation = {}

    def __init__(self, files):
        self.files = set(files)
        self.parse_to_dict(self.files)

    def parse_to_dict(self, files):
        for file in files:
            current_file_key_val = {}
            with open(file, "rt") as f:
                for line in f:
                    l = line.strip()
                    if l and not l.startswith(self.comment_char):
                        key_value_split = l.split(self.separator)
                        key = key_value_split[0].strip()
                        value = self.separator.join(key_value_split[1:]).strip().strip('"')
                        if value:
                            current_file_key_val[key] = value
            self.dict_representation[file] = current_file_key_val

    def get_as_dictionary(self):
        return self.dict_representation


class Bundle(object):
    whoami = __qualname__

    def __init__(self, path, extension, files, default_locale=None):
        self.path = path
        self.extension = extension
        self.files = set(files)
        self.default_locale = default_locale or "en_US"
        # Processing related variables
        self.snapshot_file = ''
        self.default_locale_file = ''
        self.bundle_as_dictionary = {}
        self.missing_items = {}
        self.added_items = {}

    def get_default_locale_file(self):
        if self.default_locale_file:
            return self.default_locale_file

        locale_regex_match = []
        for file in self.files:
            '''
                This regex matches all files that have _{default_locale} in their
                filename but not if that file also contains the word snapshot. This
                is to prevent the regex matching of the snapshot file when looking
                for the default locale file
            '''
            if re.match(rf'.*_{self.default_locale}(?!(.*snapshot)).*', file):
                locale_regex_match.append(file)
        if len(locale_regex_match) > 1:
            sys.exit(
                f'{self.whoami}: There were multiple regex matches of '
                + f'_{self.default_locale} in {self.path}: {locale_regex_match}. '
                + f'Expecting only a single match'
            )
        elif len(locale_regex_match) == 0:
            sys.exit(
                f'{self.whoami}: Expected default locale file to match regex '
                + f'.*_{self.default_locale} but no files in {self.path} matched'
            )
        else:
            return locale_regex_match[0]

    def get_snapshot_file(self):
        if self.snapshot_file:
            return self.snapshot_file

        default_locale_path = self.get_default_locale_file()
        snapshot_file_path = ''.join((default_locale_path, '.snapshot'))
        if not os.path.exists(snapshot_file_path):
            print(
                f'generating snapshot file {snapshot_file_path} '
                + f'based on {default_locale_path}'
            )
            with open(snapshot_file_path, 'a') as snap, open(default_locale_path, 'r') as default:
                for line in default:
                    snap.write(line)
        if snapshot_file_path not in self.files:
            self.files.add(snapshot_file_path)
        return snapshot_file_path

    def convert_to_dictionary(self):
        if self.bundle_as_dictionary:
            return self.bundle_as_dictionary

        if self.extension == 'json':
            self.bundle_as_dictionary = JsonProcessor(self.files).get_as_dictionary()
        elif self.extension == 'properties':
            self.bundle_as_dictionary = PropertiesProcessor(self.files).get_as_dictionary()
        else:
            sys.exit(
                f'{self.whoami}: Bundle type of {self.extension} is not one of the supported types')
        return self.bundle_as_dictionary

    # Find all items that exist in the snapshot but not in a locale file
    def get_missing_items_in_bundle(self):
        bundle_as_dictionary = self.convert_to_dictionary()
        snapshot_file = self.get_snapshot_file()
        snapshot = bundle_as_dictionary[snapshot_file]
        for file in bundle_as_dictionary.keys():
            candidate = bundle_as_dictionary[file]
            missing = {key: val for key, val in snapshot.items() if key not in candidate.keys()}
            if missing:
                self.missing_items[file] = missing
        return self.missing_items

    # Find all items that exist in the default locale file but not the snapshot
    def get_added_items_in_bundle(self):
        bundle_as_dictionary = self.convert_to_dictionary()
        snapshot_file = self.get_snapshot_file()
        snapshot = bundle_as_dictionary[snapshot_file]
        default_locale_file = self.get_default_locale_file()
        default = bundle_as_dictionary[default_locale_file]

        if default != snapshot:
            new_values = {key: val for key, val in default.items() if default[key] not in snapshot.values()}
            '''
                TODO: Ignoring the capability to actually make an inplace
                edit on the default locale file for any key value pair.
                With the logic currently implemented, this will show up
                simply as a "new addition" and the snapshot file will
                become stale with the old key that was actually "removed"
                in the default locale file. How do we reconcile this?
            '''
            if new_values:
                self.added_items[default_locale_file] = new_values
        return self.added_items


class Bundler:
    all_bundles = []

    def add_to_all_bundles(self, bundle):
        path = bundle.get('path')
        extension = bundle.get('extension')
        default_locale = bundle.get('default_locale')
        resolved_path = Utilities.resolve_path(path)
        all_files_in_bundle_path = []
        for file in os.listdir(resolved_path):
            if file.endswith(extension):
                file_path = os.path.join(resolved_path, file)
                all_files_in_bundle_path.append(file_path)
        bundle_object = Bundle(path=resolved_path, extension=extension, files=all_files_in_bundle_path,
                               default_locale=default_locale)
        self.all_bundles.append(bundle_object)

    def gather(self, data):
        for bundle in data.get('bundles'):
            self.add_to_all_bundles(bundle)
        for bundle_obj in self.all_bundles:
            bundle_obj.get_snapshot_file()
        return self.all_bundles


class TranslationGenerator:
    '''
        Accepts a list of Bundle objects and apply the necessary parser
        to generate all the differences between the default_locale, it's corresponding
        snapshot and all the other locales
    '''
    whoami = __qualname__
    all_bundles = []
    additions = []
    missing = []

    def __init__(self, options, all_bundles, exporter):
        self.options = options
        self.all_bundles = all_bundles
        self.exporter = exporter

    def generate_all(self):
        for bundle in self.all_bundles:
            missing_items = bundle.get_missing_items_in_bundle()
            added_items = bundle.get_added_items_in_bundle()
            if missing_items:
                self.missing.append(missing_items)
            if added_items:
                self.additions.append(added_items)
        Manifest(self.options).print_manifest(self.missing, self.additions)
        self.exporter.generate_request(self.missing, self.additions)


class Manifest:
    data = {}

    def __init__(self, options):
        self.options = options

    def print_manifest(self, missing, additions):
        for added in additions:
            self.data["added"] = self.data.get("added") or []
            self.data["added"].append(added)
        for missed in missing:
            self.data["missing"] = self.data.get("missing") or []
            self.data["missing"].append(missed)

        if self.options.output == 'json' and self.data:
            print(json.dumps(self.data, indent=4))
        elif self.options.output == 'yaml' and self.data:
            print(yaml.dump(self.data))


class Reconciliator:
    '''
        Accepts a list of bundle objects and self-heals every
        file in each bundle with their respective snapshot/default
        locale files. Intended to be run often to preserve the correct
        state of all the files
    '''
    whoami = __qualname__

    def __init__(self, options, all_bundles):
        self.options = options
        self.all_bundles = all_bundles

    def reconcile(self):
        for bundle in self.all_bundles:
            self.balance(bundle)

    def balance(self, bundle):
        snapshot = bundle.get_snapshot_file()

    def alphabetize(self, file):
        return


class Validator:
    whoami = __qualname__

    def validate(self, data):
        ACCEPTED_FILE_TYPES = {'properties', 'json'}
        if data and 'bundles' in data and data.get('bundles'):
            for bundle in data.get('bundles'):
                self.validate_keys_in_bundle(bundle)
                path = Utilities.resolve_path(bundle.get('path'))
                if not os.path.exists(path):
                    sys.exit(
                        f'{self.whoami}: {path} does not exist'
                    )
                extension = bundle.get('extension')
                if extension not in ACCEPTED_FILE_TYPES:
                    sys.exit(
                        f'{self.whoami}: .{extension} files are not one of the supported types\n' +
                        ', '.join(sorted(ACCEPTED_FILE_TYPES))
                    )
                for fname in os.listdir(path):
                    if fname.endswith(extension):
                        break
                else:
                    sys.exit(f'{self.whoami}: no .{extension} file found in {path}')
        else:
            sys.exit(f'{self.whoami}: {config_file} does not have any bundles')

    def validate_keys_in_bundle(self, bundle):
        REQUIRED_KEYS = {'path', 'extension'}
        if REQUIRED_KEYS - set(bundle.keys()):
            sys.exit(
                f'{self.whoami}: bundle configuration must have keys ' +
                ', '.join(sorted(REQUIRED_KEYS)))


class Utilities:
    @staticmethod
    def resolve_path(path):
        return os.path.realpath(path)


class ConfigUtilities:
    @staticmethod
    def get_value(config, keys):
        return ConfigUtilities.get_value(config[keys[0]], keys[1:]) if keys else config


class TranslationRequestGenerator(ABC):
    @abstractmethod
    def __init__(self, config):
        pass

    @abstractmethod
    def generate_request(self, missing, additions):
        pass


class TranslationResponseProcessor(ABC):
    @abstractmethod
    def __init__(self, config):
        pass

    @abstractmethod
    def process_response(self):
        pass


if __name__ == '__main__':
    try:
        Driver().main()
    except KeyboardInterrupt:
        exit(130)
