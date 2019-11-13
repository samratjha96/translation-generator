import argparse
import os
import sys
import yaml

whoami = os.path.basename(sys.argv[0])

class Generator:
    LOCKFILE = 'translation-config.yml'

    def main(self, args=sys.argv[1:], prog=whoami):
        options = self.parse_args(args, prog)
        allow_changes = options.generate
        self.process(allow_changes)
        #self.test_execution()

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
        if os.path.exists(self.LOCKFILE):
            with open(self.LOCKFILE, 'r') as f:
                data = yaml.full_load(f)
        return data

    def validate_keys_in_bundle(self, bundle):
       REQUIRED_KEYS = {'path', 'extension'}
       if REQUIRED_KEYS - set(bundle.keys()):
           sys.exit(
               f'{whoami}: bundle configuration must have keys ' +
                ', '.join(sorted(REQUIRED_KEYS)))

    def is_valid_configuration(self, data):
        ACCEPTED_FILE_TYPES = {'properties', 'json'}
        if data and 'bundles' in data:
            for bundle in data['bundles']:
                self.validate_keys_in_bundle(bundle)
                path = self.resolve_path(bundle['path'])
                if not os.path.exists(path):
                    sys.exit(
                        f'{whoami}: {path} does not exist'
                    )
                extension = bundle['extension']
                if extension not in ACCEPTED_FILE_TYPES:
                    sys.exit(
                        f'{whoami}: .{extension} files are not one of the supported types\n' +
                        ', '.join(sorted(ACCEPTED_FILE_TYPES))
                    )
                found = False
                for fname in os.listdir(path):
                    if fname.endswith(extension):
                        found = True
                        break
                if not found:
                    sys.exit(f'{whoami}: no .{extension} file found in {path}')    
        else:
            sys.exit(f'{whoami}: {self.DATAFILE} does not have any bundles')
        return True
    
    def parse_bundle(self, bundle):
        path = bundle['path']
        extension = bundle['extension']
        resolved_path = self.resolve_path(path)
        for file in os.listdir(resolved_path):
            if file.endswith(extension):
                print(os.path.join(resolved_path, file))

    def resolve_path(self, path):
        return os.path.realpath(path)

    def process(self, allow_changes):
        data = self.load_config()
        valid = self.is_valid_configuration(data)
        if valid:
            for bundle in data['bundles']:
                self.parse_bundle(bundle)
    
    # Only to test execution of certain methods
    def test_execution(self):
        self.process(True)

if __name__ == '__main__':
    try:
        Generator().main()
    except KeyboardInterrupt:
        exit(130)
