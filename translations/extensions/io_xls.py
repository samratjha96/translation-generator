import datetime
import glob
import os
import shutil
import sys
import zipfile
import pandas as pd

from openpyxl import Workbook
from translations.translator import TranslationRequestGenerator, TranslationResponseProcessor, ConfigUtilities


class Constants:
    DEFAULT_TRANSL_XLS_PATH = 'translations-xls/'
    DEFAULT_TRANSL_PKG_NAME = 'translations'
    WORKING_DIR = 'translations-wrk/'
    DIST_PATH = 'translations-out/'


class XlsExporter(TranslationRequestGenerator):
    whoami = __qualname__

    def __init__(self, config):
        self.default_locale = ConfigUtilities.get_value(config, ('locales', 'default'))
        self.supported_locales = ConfigUtilities.get_value(config, ('locales', 'supported'))
        self.out_name = ConfigUtilities.get_value(config, ('io', 'out', 'name'))
        self.export_mapping = ConfigUtilities.get_value(config, ('io', 'out', 'mapping'))
        IOUtilities.init_dir(Constants.DEFAULT_TRANSL_XLS_PATH)

    def generate_request(self, manifest):
        target_translations = {}
        for locale in self.supported_locales:
            locale_out_target = self.get_locale_out_target(locale)
            if locale_out_target:
                print(f'Processing added messages for locale "{locale}" to be included on export "{locale_out_target}"')
                if locale_out_target in target_translations:
                    translations = target_translations[locale_out_target]
                else:
                    translations = []

                for bundles in manifest.data.additions:
                    for bundle_path in bundles:
                        messages = bundles[bundle_path]
                        for message in messages.values():
                            if message not in translations:
                                translations.append(message)
                target_translations[locale_out_target] = translations
            else:
                print(f'Processing added messages for locale "{locale}" was ignored')

        for resources in manifest.data.missing:
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
        self.translations_pkg = ConfigUtilities.get_value(config, ('io', 'in', 'package'))
        self.import_mapping = ConfigUtilities.get_value(config, ('io', 'in', 'mapping'))

    def process_response(self, manifest):
        self.unzip_excel_files()
        manifest.print()
        for missing in manifest.data.get('missing'):
            print(f'Missing: {missing}')

    def unzip_excel_files(self):
        try:
            with zipfile.ZipFile(self.translations_pkg, 'r') as zip_ref:
                zip_ref.extractall(Constants.WORKING_DIR)

            # Normalize translations provided to CSV files
            files = glob.glob(Constants.WORKING_DIR + '**/*.xls', recursive=True) + \
                    glob.glob(Constants.WORKING_DIR + '**/*.xlsx', recursive=True)
            for file in files:
                data = pd.read_excel(file)
                # ToDo: Future enhancement: support the possibility of multiple sources for the same locale
                data.to_csv(Constants.WORKING_DIR + data.columns[1] + '.csv', encoding='utf-8')
        except:
            sys.exit(f'{self.whoami}: Translations ZIP package "{self.translations_pkg}" not found')

    def read_translations_csv(self, csv_file_path, target_locale):
        translations_dict = {}
        locale_translations_csv = pd.read_csv(csv_file_path, encoding='utf8')
        for i in locale_translations_csv.index:
            translation = locale_translations_csv[target_locale][i]
            # Source message is located in first column
            translations_dict[locale_translations_csv[0][i]] = translation
        return translations_dict


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
