import json
import os
import shutil


class Utilities:
    @staticmethod
    def print_data(data):
        print(json.dumps(data, indent=4))

    @staticmethod
    def init_dir(path):
        if os.path.exists(path):
            shutil.rmtree(path)
        os.mkdir(path)

    @staticmethod
    def get_locale_from_path(path, supported_locales):
        path_wo_extension = path[:path.rfind('.')]
        for locale in supported_locales:
            if path_wo_extension.endswith(locale):
                return locale
        return None

    @staticmethod
    def replace_locale_in_path(path, old_locale, new_locale):
        if path.find(old_locale):
            first, sep, last = path.rpartition(old_locale)
            return first + new_locale + last
        first, sep, last = path.rpartition('.')
        return first + '_' + new_locale + '.' + last

    @staticmethod
    def get_unicode_markup(content):
        return content.encode('unicode-escape').decode('utf-8').replace('\\x', '\\u00')

    @staticmethod
    def write_to_json_file(name, content):
        with open(name + '.json', 'w') as outfile:
            json.dump(content, outfile, ensure_ascii=False, indent=2)
            outfile.write('\n')

    @staticmethod
    def confirm(question, options):
        reply = str(input(question + ' (' + '/'.join(options) + ') ')).lower().strip()
        if reply[0] in options:
            return reply[0]
        else:
            return Utilities.confirm('Please use one of the valid options:', options)
