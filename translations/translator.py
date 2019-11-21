import argparse
import importlib
import os
import sys
import re
import yaml
import json

from abc import ABC, abstractmethod

from translations.utils import Utilities, ConfigUtilities

program = os.path.basename(sys.argv[0])
config_file = 'translation-config.yml'


class Driver:
    whoami = __qualname__

    def main(self, args=sys.argv[1:], prog=program):
        options = self.parse_args(args, prog)
        config = self.load_config()
        Validator().validate(config)
        exporter = self.instantiate_exporter(config, options)
        importer = self.instantiate_importer(config, options)
        all_bundles = Bundler().gather(config)

        manifest = TranslationGenerator(options, all_bundles).generate()
        if options.export:
            exporter.generate_request(manifest)
        if options.import_translations:
            translation_updates, new_messages = importer.process_response(manifest)
            TranslationUpdater.update(translation_updates)
            SnapshotUpdater(config).update(manifest, new_messages)
            Utilities.write_to_json_file('translations-manifest', manifest.data)
            Utilities.write_to_json_file('translations-updates', translation_updates)
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

        parser.add_argument('-d', '--dump',
                            help='enable process to dump output files providing information about the execution',
                            action='store_true',
                            default=False)

        mode = parser.add_mutually_exclusive_group(required=True)
        mode.add_argument('-e', '--export',
                          help='generate export of pending translations',
                          action='store_true',
                          default=False)
        mode.add_argument('-i', '--import-translations',
                          dest='import_translations',
                          help='import translations',
                          action='store_true',
                          default=False)
        mode.add_argument('--reconcile',
                          help='sanitize locale files',
                          action='store_true',
                          default=False)
        return parser.parse_args(args)

    def load_config(self):
        if not os.path.exists(config_file):
            sys.exit(f'{self.whoami}: configuration file "{config_file}" not found')
        with open(config_file, 'r') as f:
            data = yaml.full_load(f)
        return data

    def instantiate_exporter(self, config, options):
        exporter_class_fqn = ConfigUtilities.get_value(config, ('io', 'out', 'generator'))
        exporter_class = self.get_class(exporter_class_fqn)
        return exporter_class(config, options)

    def instantiate_importer(self, config, options):
        importer_class_fqn = ConfigUtilities.get_value(config, ('io', 'in', 'importer'))
        importer_class = self.get_class(importer_class_fqn)
        return importer_class(config, options)

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

    def __init__(self, files):
        self.files = set(files)
        self.dict_representation = {}

    def parse_to_dict(self, files):
        for file in files:
            self.dict_representation[file] = ResourceFileHandler.read_json(file)

    def get_as_dictionary(self):
        self.parse_to_dict(self.files)
        return self.dict_representation


class PropertiesProcessor(object):
    '''
        Processor that can convert a properties file to a python
        dictionary keyed with the file name
    '''
    separator = '='
    comment_char = '#'

    def __init__(self, files):
        self.files = set(files)
        self.dict_representation = {}

    def parse_to_dict(self, files):
        for file in files:
            self.dict_representation[file] = ResourceFileHandler.read_properties(file)

    def get_as_dictionary(self):
        self.parse_to_dict(self.files)
        return self.dict_representation


class ResourceFileHandler:

    @staticmethod
    def read(resource_path):
        extension = resource_path[resource_path.rfind('.') + 1:]
        if extension == 'properties':
            return ResourceFileHandler.read_properties(resource_path)
        elif extension == 'json':
            return ResourceFileHandler.read_json(resource_path)
        elif extension == 'snapshot':
            return ResourceFileHandler.read(resource_path[:resource_path.rfind('.')])

        print(f'Unsupported resource extension: {extension}')
        return {}

    @staticmethod
    def read_snapshot(snapshot_path):
        orig_source = snapshot_path[:snapshot_path.rfind('.')]
        extension = orig_source[orig_source.rfind('.') + 1:]
        if extension == 'properties':
            return ResourceFileHandler.read_properties(snapshot_path)
        elif extension == 'json':
            return ResourceFileHandler.read_json(snapshot_path)
        print(f'Unsupported resource extension: {extension}')
        return {}

    @staticmethod
    def read_properties(resource_path):
        separator = '='
        comment_char = '#'

        current_file_key_val = {}
        with open(resource_path, "rt") as f:
            for line in f:
                l = line.strip()
                if l and not l.startswith(comment_char):
                    key_value_split = l.split(separator)
                    key = key_value_split[0].strip()
                    value = separator.join(key_value_split[1:]).strip().strip('"')
                    if value:
                        current_file_key_val[key] = value.encode('utf-8').decode('unicode-escape')
        return current_file_key_val

    @staticmethod
    def read_json(resource_path):
        with open(resource_path) as f:
            dictdump = json.loads(f.read())
        return dictdump

    @staticmethod
    def write(resource_path, translations):
        extension = resource_path[resource_path.rfind('.') + 1:]
        if extension == 'properties':
            ResourceFileHandler.write_properties(resource_path, translations)
        elif extension == 'json':
            ResourceFileHandler.write_json(resource_path, translations)
        else:
            print(f'Unsupported resource extension: {extension}')

    @staticmethod
    def write_snapshot(snapshot_path, messages):
        orig_source = snapshot_path[:snapshot_path.rfind('.')]
        extension = orig_source[orig_source.rfind('.') + 1:]
        if extension == 'properties':
            ResourceFileHandler.write_properties(snapshot_path, messages)
        elif extension == 'json':
            ResourceFileHandler.write_json(snapshot_path, messages)
        else:
            print(f'Unsupported resource extension: {extension}')
        return {}

    @staticmethod
    def write_properties(resource_path, messages):
        with open(resource_path, encoding='utf-8', mode='w') as outfile:
            for key in messages.keys():
                line = key + '=' + Utilities.get_unicode_markup(messages[key])
                outfile.write(line)
                outfile.write('\n')

    @staticmethod
    def write_json(resource_path, messages):
        with open(resource_path, 'w') as outfile:
            json.dump(messages, outfile, ensure_ascii=False, indent=2)
            outfile.write('\n')


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

    def __init__(self, options, all_bundles):
        self.options = options
        self.all_bundles = all_bundles

    def generate(self):
        manifest = Manifest(self.options)
        for bundle in self.all_bundles:
            missing_items = bundle.get_missing_items_in_bundle()
            added_items = bundle.get_added_items_in_bundle()
            if missing_items:
                self.missing.append(missing_items)
            if added_items:
                self.additions.append(added_items)
        manifest.build(self.missing, self.additions)
        return manifest


class TranslationUpdater:
    whoami = __qualname__

    @staticmethod
    def update(translations):
        for resource_path, translations in translations.items():
            resource_translations = ResourceFileHandler.read(resource_path)
            for key, translation in translations.items():
                if translation is not None:
                    resource_translations[key] = translation
            ResourceFileHandler.write(resource_path, resource_translations)


class SnapshotUpdater:
    whoami = __qualname__

    def __init__(self, config):
        self.default_locale = ConfigUtilities.get_value(config, ('locales', 'default'))
        self.copy_to_locales = ConfigUtilities.get_value(config, ('snapshots', 'copy_to'))

    def update(self, manifest, new_messages):
        added = manifest.data.get('added')
        if added:
            for resource in added:
                for source_path, messages in resource.items():
                    if source_path in new_messages.keys():
                        source_new_messages = new_messages[source_path]
                        snapshot_path = source_path + '.snapshot'
                        snapshot = ResourceFileHandler.read_snapshot(snapshot_path)
                        for key, message in source_new_messages.items():
                            snapshot[key] = message
                        ResourceFileHandler.write_snapshot(snapshot_path, snapshot)
                        for copy_to_locale in self.copy_to_locales:
                            print(f'Copying snapshot "{snapshot_path}" content to locale {copy_to_locale}\'s resource.')
                            ResourceFileHandler.write(
                                Utilities.replace_locale_in_path(source_path, self.default_locale, copy_to_locale),
                                snapshot)


class Manifest:
    data = {}

    def __init__(self, options):
        self.options = options

    def build(self, missing, additions):
        for added in additions:
            self.data["added"] = self.data.get("added") or []
            self.data["added"].append(added)
        for missed in missing:
            self.data["missing"] = self.data.get("missing") or []
            self.data["missing"].append(missed)

    def print(self):
        if self.options.output == 'json' and self.data:
            print(json.dumps(self.data, indent=4))
        elif self.options.output == 'yaml' and self.data:
            print(yaml.dump(self.data))

    def copy(self):
        return self.data.copy()


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


class TranslationRequestGenerator(ABC):
    @abstractmethod
    def __init__(self, config, options):
        pass

    @abstractmethod
    def generate_request(self, manifest):
        pass


class TranslationResponseProcessor(ABC):
    @abstractmethod
    def __init__(self, config, options):
        pass

    @abstractmethod
    def process_response(self, manifest):
        pass
