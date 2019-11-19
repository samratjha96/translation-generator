import json
import os
import shutil

from openpyxl import Workbook

from translator import TranslationRequestGenerator


class Constants:
    DEFAULT_TRANSL_XLS_PATH = 'translations-xls/'
    DEFAULT_TRANSL_PKG_NAME = 'translations'
    DIST_PATH = 'translations-out/'


class XlsExporter(TranslationRequestGenerator):
    whoami = __qualname__

    def __init__(self, config):
        self.default_locale = config.get('locales').get('default')
        self.supported_locales = config.get('locales').get('supported')
        self.export_mapping = config.get('io-mapping').get('out')
        self.import_mapping = config.get('io-mapping').get('in')
        Utilities.init_dir(Constants.DEFAULT_TRANSL_XLS_PATH)

    def generate_request(self, missing, additions):
        target_translations = {}
        for locale in self.supported_locales:
            locale_out_target = self.get_locale_out_target(locale)
            if locale_out_target:
                print(f'Processing added messages for locale "{locale}" to be included on export "{locale_out_target}"')
                if locale_out_target in target_translations:
                    translations = target_translations[locale_out_target]
                else:
                    translations = []

                for bundles in additions:
                    for bundle_path in bundles:
                        messages = bundles[bundle_path]
                        for message in messages.values():
                            if message not in translations:
                                translations.append(message)
                target_translations[locale_out_target] = translations
            else:
                print(f'Processing added messages for locale "{locale}" was ignored')

        for resources in missing:
            for resource_path in resources:
                locale = Utilities.get_locale_from_path(resource_path, self.supported_locales)
                locale_out_target = self.get_locale_out_target(locale)
                if locale_out_target:
                    print(f'Processing missing messages in locale "{locale}" to be included on export "{locale_out_target}"')
                    if locale_out_target in target_translations:
                        translations = target_translations[locale_out_target]
                    else:
                        translations = []
                    messages = resources[resource_path]
                    for message in messages.values():
                        if message not in translations:
                            translations.append(message)
                    target_translations[locale_out_target] = translations
                else:
                    print(f'Processing missing messages for locale "{locale}" was ignored')

        for target in target_translations:
            print(f'Writing locale "{target}" with "{len(target_translations[target])}" translations')
            self.write_xls(target, target_translations[target])

    def get_locale_out_target(self, locale):
        if locale in self.export_mapping:
            return self.export_mapping[locale]
        return locale

    def write_xls(self, locale, translations, postfix=None, context_col_value=None):
        workbook = Workbook()
        sheet = workbook.active

        sheet['A1'] = 'en_US'
        sheet['B1'] = locale
        sheet['C1'] = 'CONTEXT'
        sheet['D1'] = 'CONTEXT_DESCRIPTION'
        row = 2

        for translation in translations:
            sheet[f'A{row}'] = translation
            sheet[f'C{row}'] = context_col_value if context_col_value else ''
            row += 1

        workbook.save(Constants.DEFAULT_TRANSL_XLS_PATH + locale + ('-' + postfix if postfix else '') + '.xls')


class Utilities:
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
