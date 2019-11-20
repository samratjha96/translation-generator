import datetime
import glob
import shutil
import sys
import zipfile
import pandas as pd

from openpyxl import Workbook
from translations.translator import TranslationRequestGenerator, TranslationResponseProcessor
from translations.utils import ConfigUtilities, Utilities


class Constants:
    DEFAULT_TRANSL_XLS_PATH = 'translations-xls/'
    DEFAULT_TRANSL_PKG_NAME = 'translations'
    WORKING_DIR = 'translations-wrk/'
    DIST_PATH = 'translations-out/'
    SNAPSHOT_SENTINEL = '__SNAPSHOT__'


class XlsExporter(TranslationRequestGenerator):
    whoami = __qualname__

    def __init__(self, config):
        self.default_locale = ConfigUtilities.get_value(config, ('locales', 'default'))
        self.supported_locales = ConfigUtilities.get_value(config, ('locales', 'supported'))
        self.out_name = ConfigUtilities.get_value(config, ('io', 'out', 'name'))
        self.export_mapping = ConfigUtilities.get_value(config, ('io', 'out', 'mapping'))
        Utilities.init_dir(Constants.DEFAULT_TRANSL_XLS_PATH)

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
        self.expected_locales = self.determine_expected_locales()

    def determine_expected_locales(self):
        expected_locales = self.supported_locales.copy()
        for inbound_locale, mapped_locales in self.import_mapping.items():
            expected_locales = [locale for locale in expected_locales if locale not in mapped_locales]
            if inbound_locale not in expected_locales and inbound_locale != Constants.SNAPSHOT_SENTINEL:
                expected_locales.append(inbound_locale)
        print(expected_locales)
        return expected_locales

    def process_response(self, manifest):
        translations = XlsTranslationsProcessor.get_inbound_translations(self.translations_pkg,
                                                                         self.default_locale,
                                                                         self.expected_locales)
        Utilities.print_data(translations)
        # for missing in manifest.data.get('missing'):
        #     print(f'Missing: {missing}')


class XlsTranslationsProcessor:
    @staticmethod
    def get_inbound_translations(translations_pkg, source_locale, locales):
        translations = {}
        try:
            with zipfile.ZipFile(translations_pkg, 'r') as zip_ref:
                zip_ref.extractall(Constants.WORKING_DIR)
        except:
            sys.exit(f'Translations ZIP package "{translations_pkg}" not found')

        files = glob.glob(Constants.WORKING_DIR + '**/*.xls', recursive=True) + \
                glob.glob(Constants.WORKING_DIR + '**/*.xlsx', recursive=True)
        for file in files:
            locale = Utilities.get_locale_from_path(file, locales)
            print(f'Processing translations for {locale}, from {source_locale}, in file {file}')
            translations_data = pd.read_excel(file)
            # Validate
            if translations_data[source_locale] is None:
                print(f'Translations in "{file}" does not have a dedicated column for source locale "{source_locale}')
            if translations_data[locale] is None:
                print(f'Translations in "{file}" does not have a dedicated column for locale "{locale}')

            if locale not in translations:
                translations[locale] = {}
            for i in translations_data.index:
                message = translations_data[source_locale][i]
                translation = translations_data[locale][i]
                translations[locale][message] = translation

        return translations
