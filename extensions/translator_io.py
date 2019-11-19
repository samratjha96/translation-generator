import json
import os

import yaml
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
        print(json.dumps(self.export_mapping, indent=2))

    def generate_request(self, missing, additions):
        for bundles in additions:
            for bundle_path in bundles:
                messages = bundles[bundle_path]
                for message in messages:
                    print(f'Processing new message: {message}')
        for resources in missing:
            for resource_path in resources:
                locale = Utilities().get_locale_from_path(resource_path, self.supported_locales)
                messages = resources[resource_path]
                for message in messages:
                    print(f'Processing message: {message} in locale {locale}')

        # target_translations = {}
        # for locale in self.supported_locales:
        #     locale_source = locale['source']
        #     locale_target = locale['target']
        #     if locale_target is not None:
        #         print(f'Processing locale "{locale_source}" to be included on export "{locale_target}"')
        #         if locale_target in target_translations:
        #             translations = target_translations[locale_target]
        #         else:
        #             translations = []
        #
        #         for resource in lock_file_contents['project_i18n_resources'].values():
        #             pending_translations = resource['pending_translations']
        #             for new in pending_translations['new'].values():
        #                 add_translation(translations, new)
        #             for updated in pending_translations['updated'].values():
        #                 add_translation(translations, updated)
        #
        #             if locale_source in pending_translations['missing']:
        #                 for missing in pending_translations['missing'][locale_source].values():
        #                     add_translation(translations, missing)
        #
        #         target_translations[locale_target] = translations
        #     else:
        #         print(f'Locale "{locale_source}" ignored')
        #
        # for target in target_translations:
        #     print(f'Writing locale "{target}" with "{len(target_translations[target])}" translations')
        #     write_xls(target, target_translations[target], args.postfix, args.context_col_value)

    def write_xls(self, locale, translations, postfix, context_col_value):
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
    def get_locale_from_path(self, path, supported_locales):
        path_wo_extension = path[:path.rfind('.')]
        for locale in supported_locales:
            if path_wo_extension.endswith(locale):
                return locale
        return None

