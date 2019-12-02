import argparse
import glob
import importlib
import os
import sys
import re
import yaml
import json

from abc import ABC, abstractmethod

from translations.utils import Utilities

program = os.path.basename(sys.argv[0])


class Driver:
    whoami = __qualname__

    def main(self, args=sys.argv[1:], prog=program):
        options = self.parse_args(args, prog)
        config = Config()
        if options.command == 'init':
            if not options.init_locale:
                sys.exit(f'{self.whoami}: cannot initialize if initialization locale is not provided')
            config.init(options.init_locale, options.source_paths)
        elif options.command == 'clean':
            if not options.init_locale:
                sys.exit(f'{self.whoami}: cannot clean resource snapshots if initialization locale is not provided')
            config.clean(options.init_locale, options.source_paths)
        else:
            config.load_config()
            config.validate()
            all_bundles = Bundler().gather(config)
            manifest = ManifestGenerator.generate(options, all_bundles)

            if options.command == 'view':
                Utilities.print_data(manifest.data)
            elif options.command == 'export':
                exporter = self.instantiate_exporter(config, options)
                if exporter:
                    exporter.generate_request(manifest)
                else:
                    print('No exporter defined in configuration file')
            elif options.command == 'import':
                importer = self.instantiate_importer(config, options)
                if importer:
                    translation_updates, new_messages = importer.process_response(manifest)
                    TranslationUpdater.update(translation_updates)
                    SnapshotUpdater(config).update(manifest, new_messages)
                    Utilities.write_to_json_file('translations-manifest', manifest.data)
                    Utilities.write_to_json_file('translations-updates', translation_updates)
                else:
                    print('No importer defined in configuration file')
            elif options.command == 'reconcile':
                Reconciliator(options, all_bundles).reconcile()
            else:
                sys.exit(f'{self.whoami}: invalid command "{options.command}" provided; likely a programmer error.')

    def parse_args(self, args, prog):
        parser = argparse.ArgumentParser(
            prog=prog,
            description='Generator for candidate translation strings',
        )
        parser.add_argument('command',
                            choices=('init', 'clean', 'view', 'export', 'import', 'reconcile'),
                            help='command to run')

        # arguments specific for 'view' and 'clean' commands
        init_args = parser.add_argument_group()
        init_args.add_argument('-l', '--source-locale',
                               help='define the locale that will serve as the source locale for the configuration',
                               dest='init_locale',
                               default=None)
        init_args.add_argument('-s', '--source-path',
                               nargs='+',
                               dest='source_paths',
                               help='list relative paths of where to look for translation bundles',
                               default=['.'],
                               type=str)

        # arguments applicable to any command
        parser.add_argument('--output',
                            help='output type',
                            choices=('yaml', 'json'),
                            default='yaml')
        parser.add_argument('-d', '--dump',
                            help='enable process to dump output files providing information about the execution',
                            action='store_true',
                            default=False)

        return parser.parse_args(args)

    def instantiate_exporter(self, config, options):
        try:
            exporter_class_fqn = config.get_value(('export', 'generator'))
            exporter_class = self.get_class(exporter_class_fqn)
            return exporter_class(config, options)
        except:
            return None

    def instantiate_importer(self, config, options):
        try:
            importer_class_fqn = config.get_value(('import', 'importer'))
            importer_class = self.get_class(importer_class_fqn)
            return importer_class(config, options)
        except:
            return None

    def get_class(self, class_fqn):
        module_name = class_fqn[:class_fqn.rfind('.')]
        class_name = class_fqn[class_fqn.rfind('.') + 1:]
        io_module = importlib.import_module(module_name)
        return getattr(io_module, class_name)


class Config:
    whoami = __qualname__
    config_file = 'translation-config.yml'
    supported_file_types = {'properties', 'json'}
    data = None

    def init(self, init_locale, source_paths):
        self.data = {
            'locales': {
                'default': init_locale,
            }
        }
        supported_locales = []
        bundles = []
        files = []
        for source_path in source_paths:
            for supported_file in self.supported_file_types:
                if source_path[-1:] != '/':
                    source_path = source_path + '/'
                files = files + glob.glob(f'{source_path}**/*[-_]{init_locale}.{supported_file}', recursive=True)
        for file in files:
            bundles.append({
                'source': file
            })
            bundle_path, source_locale, bundle_extension, bundle_resources = ResourceFileHandler.get_bundle_elements(file)
            for locale_resource in bundle_resources:
                supported_locale = ResourceFileHandler.get_resource_locale(locale_resource, bundle_path, bundle_extension)
                if supported_locale:
                    if supported_locale != init_locale and supported_locale not in supported_locales:
                        supported_locales.append(supported_locale)
                else:
                    print(f'Did not find locale in path "{locale_resource}"')
        self.data['locales']['supported'] = supported_locales
        self.data['bundles'] = bundles
        # Utilities.print_data(self.data)
        with open(self.config_file, 'w') as outfile:
            yaml.dump(self.data, outfile)
            outfile.write('\n')

    def clean(self, init_locale, source_paths):
        print(f'{self.whoami}: searching for resource snapshots by initialization locale "{init_locale}"...')
        files = []
        for source_path in source_paths:
            for supported_file_type in self.supported_file_types:
                if source_path[-1:] != '/':
                    source_path = source_path + '/'
                files = files + glob.glob(f'{source_path}**/*[-_]{init_locale}.{supported_file_type}.snapshot', recursive=True)
        if len(files) > 0:
            reply = Utilities.confirm(f'{self.whoami}: Found "{len(files)}" '
                                      f'snapshots to clear; delete [a]ll or [c]onfirm each?', ['a', 'c'])
            for file in files:
                if reply == 's':
                    break
                if reply != 'a':
                    reply = Utilities.confirm(f'{self.whoami}: Delete snapshot: "{file}" [y]es, [n]o, [a]ll, or [s]top?', ['y', 'n', 'a', 's'])
                if reply == 'y' or reply == 'a':
                    os.remove(file)

    def load_config(self):
        if not os.path.exists(self.config_file):
            sys.exit(f'{self.whoami}: configuration file "{self.config_file}" not found')
        with open(self.config_file, 'r') as f:
            self.data = yaml.full_load(f)

    def validate(self):
        try:
            self.get_value(('locales', 'default'))
        except:
            sys.exit(f'{self.whoami}: config file "{self.config_file}" does not have a default locale defined')
        try:
            self.get_value(('locales', 'supported'))
        except:
            sys.exit(f'{self.whoami}: config file "{self.config_file}" does not have supported locales defined')

        try:
            for bundle in self.get_value('bundles'):
                source = bundle.get('source')
                if not os.path.exists(source):
                    # ToDo: Logger impl - set as WARN
                    print(f'{self.whoami}: "{source}" does not exist')
        except:
            sys.exit(f'{self.whoami}: {self.config_file} does not have any bundles')

    def get_value(self, keys, config=None):
        config = self.data if config is None else config
        if isinstance(keys, str):
            return config[keys]
        elif len(keys) == 1:
            return config[keys[0]]
        return self.get_value(keys[1:], config[keys[0]]) if keys else config


class JsonProcessor:
    '''
        Processor that can convert json content in files to a python
        dictionary keyed with the file name
    '''
    @staticmethod
    def get_as_dictionary(files):
        dict_representation = {}
        for file in files:
            dict_representation[file] = JsonProcessor.read(file)
        return dict_representation

    @staticmethod
    def read(resource_path):
        with open(resource_path) as f:
            dictdump = json.loads(f.read())
        return dictdump

    @staticmethod
    def write(resource_path, messages):
        print(f'Writing to file "{resource_path}"')
        with open(resource_path, encoding='utf-8', mode='w') as outfile:
            json.dump(messages, outfile, ensure_ascii=False, indent=2)
            outfile.write('\n')


class PropertiesProcessor:
    '''
        Processor that can convert a properties file to a python
        dictionary keyed with the file name
    '''
    separator = '='
    comment_char = '#'
    multiline_char = '\\'

    @staticmethod
    def get_as_dictionary(files):
        dict_representation = {}
        for file in files:
            dict_representation[file] = PropertiesProcessor.read(file)
        return dict_representation

    @staticmethod
    def read(resource_path):
        current_property = ''
        current_file_key_val = {}
        with open(resource_path, "rt") as f:
            try:
                for line in f:
                    line = line.strip()
                    if line and not current_property.startswith(PropertiesProcessor.comment_char):
                        current_property += line
                        if not line.endswith(PropertiesProcessor.multiline_char):
                            key_value_split = current_property.split(PropertiesProcessor.separator)
                            key = key_value_split[0].strip()
                            value = PropertiesProcessor.separator.join(key_value_split[1:]).strip().strip('"')
                            if value:
                                try:
                                    current_file_key_val[key] = value.encode('utf-8').decode('unicode-escape')
                                except:
                                    raise Exception(f'Failed to UTF8 encode "{value}"')
                            current_property = ''
                        else:
                            current_property = current_property[:-1]
            except Exception as err:
                print(f'Failed to process resource "{resource_path}", cause: {err}')
        return current_file_key_val

    @staticmethod
    def write(resource_path, messages):
        with open(resource_path, encoding='utf-8', mode='w') as outfile:
            for key in messages.keys():
                line = key + '=' + Utilities.get_unicode_markup(messages[key])
                outfile.write(line)
                outfile.write('\n')


class ResourceFileHandler:
    @staticmethod
    def get_bundle_elements(source):
        parts = re.split(f'[-_][a-zA-Z]{{2}}[-_][a-zA-Z]{{2}}\.', source, 1)
        bundle_path = parts[0]
        bundle_extension = parts[1]
        bundle_resources = glob.glob(f'{bundle_path}[-_][a-zA-Z][a-zA-Z][-_][a-zA-Z][a-zA-Z].{bundle_extension}') + \
                           glob.glob(f'{bundle_path}[-_][a-zA-Z][a-zA-Z].{bundle_extension}')
        default_locale = ResourceFileHandler.get_resource_locale(source, bundle_path, bundle_extension)
        return bundle_path, default_locale, bundle_extension, bundle_resources

    @staticmethod
    def get_resource_locale(resource, bundle_path, bundle_extension):
        bundle_path = bundle_path.replace('$', '\\$')
        result = re.search(
            f'{bundle_path}[-_]([a-zA-Z]{{2}}[-_][a-zA-Z]{{2}}|[a-zA-Z]{{2}}).{bundle_extension}', resource)
        return None if result is None else result.group(1)

    @staticmethod
    def read(resource_path):
        extension = resource_path[resource_path.rfind('.') + 1:]
        if extension == 'properties':
            return PropertiesProcessor.read(resource_path)
        elif extension == 'json':
            return JsonProcessor.read(resource_path)
        elif extension == 'snapshot':
            return ResourceFileHandler.read(resource_path[:resource_path.rfind('.')])

        print(f'Unsupported resource extension: {extension}')
        return {}

    @staticmethod
    def read_snapshot(snapshot_path):
        orig_source = snapshot_path[:snapshot_path.rfind('.')]
        extension = orig_source[orig_source.rfind('.') + 1:]
        if extension == 'properties':
            return PropertiesProcessor.read(snapshot_path)
        elif extension == 'json':
            return JsonProcessor.read(snapshot_path)
        print(f'Unsupported resource extension: {extension}')
        return {}

    @staticmethod
    def write(resource_path, translations):
        extension = resource_path[resource_path.rfind('.') + 1:]
        if extension == 'properties':
            PropertiesProcessor.write(resource_path, translations)
        elif extension == 'json':
            JsonProcessor.write(resource_path, translations)
        else:
            print(f'Unsupported resource extension: {extension}')

    @staticmethod
    def write_snapshot(snapshot_path, messages):
        orig_source = snapshot_path[:snapshot_path.rfind('.')]
        extension = orig_source[orig_source.rfind('.') + 1:]
        if extension == 'properties':
            PropertiesProcessor.write(snapshot_path, messages)
        elif extension == 'json':
            JsonProcessor.write(snapshot_path, messages)
        else:
            print(f'Unsupported resource extension: {extension}')
        return {}


class Bundle(object):
    whoami = __qualname__

    def __init__(self, source, extension, files, source_locale):
        self.source = source
        self.extension = extension
        self.files = set(files)
        self.source_locale = source_locale
        self.snapshot_file_path = self.init_snapshot(source)
        self.bundle_as_dictionary = {}
        self.missing_items = {}
        self.new_items = {}

    def init_snapshot(self, source):
        snapshot_file_path = source + '.snapshot'
        if not os.path.exists(snapshot_file_path):
            with open(snapshot_file_path, 'a') as snap, open(source, 'r') as default:
                for line in default:
                    snap.write(line)
        return snapshot_file_path

    def convert_to_dictionary(self):
        if self.bundle_as_dictionary:
            return self.bundle_as_dictionary

        if self.extension == 'json':
            self.bundle_as_dictionary = JsonProcessor.get_as_dictionary(self.files)
        elif self.extension == 'properties':
            self.bundle_as_dictionary = PropertiesProcessor.get_as_dictionary(self.files)
        else:
            sys.exit(
                f'{self.whoami}: Bundle type of {self.extension} is not one of the supported types')
        return self.bundle_as_dictionary

    # Find all items that exist in the snapshot but not in a locale file
    def get_missing_items_in_bundle(self, bundle_snapshot_data):
        bundle_as_dictionary = self.convert_to_dictionary()
        for file in bundle_as_dictionary.keys():
            candidate = bundle_as_dictionary[file]
            missing = {key: val for key, val in bundle_snapshot_data.items() if key not in candidate.keys()}
            if missing:
                self.missing_items[file] = missing
        return self.missing_items

    # Find all items that exist in the default locale file but not the snapshot
    def get_new_items_in_bundle(self, bundle_snapshot_data):
        bundle_as_dictionary = self.convert_to_dictionary()
        default = bundle_as_dictionary[self.source]

        if default != bundle_snapshot_data:
            new_values = {key: val for key, val in default.items() if default[key] not in bundle_snapshot_data.values()}
            '''
                TODO: Ignoring the capability to actually make an inplace
                edit on the default locale file for any key value pair.
                With the logic currently implemented, this will show up
                simply as a "new addition" and the snapshot file will
                become stale with the old key that was actually "removed"
                in the default locale file. How do we reconcile this?
            '''
            if new_values:
                self.new_items[self.source_locale] = new_values
        return self.new_items


class Bundler:
    @staticmethod
    def gather(config):
        all_bundles = []
        for bundle_config in config.data.get('bundles'):
            source = bundle_config.get('source')
            extension = source[source.rfind('.')+1:]
            bundle_path, source_locale, bundle_extension, locale_resources = ResourceFileHandler.get_bundle_elements(source)
            all_bundles.append(Bundle(source, extension, locale_resources, source_locale))
        return all_bundles


class ManifestGenerator:
    '''
        Accepts a list of Bundle objects and apply the necessary parser
        to generate all the differences between the default_locale, it's corresponding
        snapshot and all the other locales
    '''
    @staticmethod
    def generate(options, all_bundles):
        new = []
        missing = []
        manifest = Manifest(options)
        for bundle in all_bundles:
            bundle_snapshot_data = ResourceFileHandler.read_snapshot(bundle.snapshot_file_path)
            missing_items = bundle.get_missing_items_in_bundle(bundle_snapshot_data)
            new_items = bundle.get_new_items_in_bundle(bundle_snapshot_data)
            if missing_items:
                missing.append(missing_items)
            if new_items:
                new.append(new_items)
        manifest.build(new, missing)
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
        self.default_locale = config.get_value(config, ('locales', 'default'))
        self.copy_to_locales = config.get_value(config, ('snapshots', 'copy_to'))

    def update(self, manifest, new_messages):
        new = manifest.get_new()
        if new:
            for resource in new:
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

    def build(self, new, missing):
        for msg in new:
            self.data['new'] = self.data.get('new') or []
            self.data['new'].append(msg)
        for msg in missing:
            self.data['missing'] = self.data.get('missing') or []
            self.data['missing'].append(msg)

    def get_new(self):
        return self.data['new'] or []

    def get_missing(self):
        return self.data['missing'] or []

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
