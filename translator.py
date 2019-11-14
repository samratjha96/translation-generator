import argparse
import os
import sys
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
    def __init__(self, path, extension, files, default_locale=None):
        self.path = path
        self.extension = extension
        self.files = set(files)
        self.default_locale = default_locale or "en_US"

class SnapshotGenerator:
    whoami = __qualname__
    all_bundles = []

    def parse_bundle(self, bundle):
        path = bundle['path']
        extension = bundle['extension']
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
        for bundle in data['bundles']:
            self.parse_bundle(bundle)

class Validator:
    whoami = __qualname__
    def validate(self, data):
        ACCEPTED_FILE_TYPES = {'properties', 'json'}
        if data and 'bundles' in data and data['bundles']:
            for bundle in data['bundles']:
                self.validate_keys_in_bundle(bundle)
                path = self.resolve_path(bundle['path'])
                if not os.path.exists(path):
                    sys.exit(
                        f'{self.whoami}: {path} does not exist'
                    )
                extension = bundle['extension']
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
