import argparse
import os
import sys
import re
import yaml

program = os.path.basename(sys.argv[0])
config_file = 'translation-config.yml'

class Driver:
    def main(self, args=sys.argv[1:], prog=program):
        options = self.parse_args(args, prog)
        generate = options.generate
        data = self.load_config()
        Validator().validate(data)
        SnapshotGenerator().process(data)

    def parse_args(self, args, prog):
        parser = argparse.ArgumentParser(
            prog=prog,
            description='Generator for candidate translation strings',
        )

        mode = parser.add_mutually_exclusive_group(required=True)
        mode.add_argument('--generate',
                          help='generate lock file',
                          action='store_true', default=False)
        return parser.parse_args(args)

    def load_config(self):
        if os.path.exists(config_file):
            with open(config_file, 'r') as f:
                data = yaml.full_load(f)
        return data

class Bundle(object):
    whoami = __qualname__
    def __init__(self, path, extension, files, default_locale=None):
        self.path = path
        self.extension = extension
        self.files = set(files)
        self.default_locale = default_locale or "en_US"

    def get_default_locale_full_path(self):
        locale_regex_match = []
        for file in self.files:
            if re.match(rf'.*_{self.default_locale}.*', file):
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

    def use_snapshot_file(self):
        default_locale_path = self.get_default_locale_full_path()
        snapshot_file_path = ''.join((default_locale_path, '.snapshot'))
        if not os.path.exists(snapshot_file_path):
            print(
                f'generating snapshot file {snapshot_file_path} '
                + f'based on {default_locale_path}'
            )
            with open(snapshot_file_path, 'a') as snap, open(default_locale_path, 'r') as default:
                for line in default:
                    snap.write(line)
        else:
            print(f'Using existing snapshot {snapshot_file_path}')
        return snapshot_file_path

class SnapshotGenerator:
    all_bundles = []

    def parse_bundle(self, bundle):
        path = bundle.get('path')
        extension = bundle.get('extension')
        default_locale = bundle.get('default_locale')
        resolved_path = Validator().resolve_path(path)
        all_files_in_bundle_path = []
        for file in os.listdir(resolved_path):
            if file.endswith(extension):
                file_path = os.path.join(resolved_path, file)
                all_files_in_bundle_path.append(file_path)
        bundle_object = Bundle(resolved_path, extension, all_files_in_bundle_path, default_locale)
        self.all_bundles.append(bundle_object)

    def process(self, data):
        for bundle in data.get('bundles'):
            self.parse_bundle(bundle)
        for bundle_obj in self.all_bundles:
            bundle_obj.use_snapshot_file()

class Validator:
    whoami = __qualname__
    def validate(self, data):
        ACCEPTED_FILE_TYPES = {'properties', 'json'}
        if data and 'bundles' in data and data.get('bundles'):
            for bundle in data.get('bundles'):
                self.validate_keys_in_bundle(bundle)
                path = self.resolve_path(bundle.get('path'))
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

    def resolve_path(self, path):
        return os.path.realpath(path)

if __name__ == '__main__':
    try:
        Driver().main()
    except KeyboardInterrupt:
        exit(130)
