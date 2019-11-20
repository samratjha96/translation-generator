import json
import os
import shutil


class Utilities:
    @staticmethod
    def resolve_path(path):
        return os.path.realpath(path)

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


class ConfigUtilities:
    @staticmethod
    def get_value(config, keys):
        return ConfigUtilities.get_value(config[keys[0]], keys[1:]) if keys else config

