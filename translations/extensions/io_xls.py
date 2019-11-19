import datetime
import os
import shutil

from openpyxl import Workbook

from translations.translator import TranslationRequestGenerator, TranslationResponseProcessor, ConfigUtilities


class Constants:
    DEFAULT_TRANSL_XLS_PATH = 'translations-xls/'
    DEFAULT_TRANSL_PKG_NAME = 'translations'
    DIST_PATH = 'translations-out/'


class XlsExporter(TranslationRequestGenerator):
    whoami = __qualname__

    def __init__(self, config):
        self.default_locale = ConfigUtilities.get_value(config, ('locales', 'default'))
        self.supported_locales = ConfigUtilities.get_value(config, ('locales', 'supported'))
        self.out_name = ConfigUtilities.get_value(config, ('io', 'out', 'name'))
        self.export_mapping = ConfigUtilities.get_value(config, ('io', 'out', 'mapping'))
        IOUtilities.init_dir(Constants.DEFAULT_TRANSL_XLS_PATH)

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
                locale = IOUtilities.get_locale_from_path(resource_path, self.supported_locales)
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

        timestamp = datetime.date.today().strftime('%Y%m%d_%H%M%S')
        print(f'Starting packaging: Using translations XLS in path "{Constants.DEFAULT_TRANSL_XLS_PATH}"')
        file_name = shutil.make_archive(Constants.DIST_PATH + self.out_name + '_' + str(timestamp),
                                        'zip',
                                        Constants.DEFAULT_TRANSL_XLS_PATH)
        print(f'Package generated in "{file_name}"')

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


class XlsImporter(TranslationResponseProcessor):
    whoami = __qualname__

    def __init__(self, config):
        self.default_locale = ConfigUtilities.get_value(config, ('locales', 'default'))
        self.supported_locales = ConfigUtilities.get_value(config, ('locales', 'supported'))
        self.import_mapping = ConfigUtilities.get_value(config, ('io', 'in', 'mapping'))

    def process_response(self):
        print(f'Processing..')


class IOUtilities:
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
