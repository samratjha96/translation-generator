# Overview
This tool is designed to easily manage internationalization aspects for a given project. 

Software projects normally rely on message bundles to define user messages that will be displayed throughout the 
application; effectively separating content from logic in the source code. Within these bundles, a localization strategy 
is used to define bundles targeted to specific (or supported) locales. A locale is commonly defined as the combination 
of the language two-character ISO code combines with the country's two-character ISO code. Using only the two-character
language code is also commonly used.

Some examples:
* `en_US`: For English in the US
* `es`: For Spanish
* `fr-ca`: For French in Canada (notice that `_` and `-` are commonly used for separating the codes).

This utilities leverages this common practice of defining message bundles, to search for these in a targeted software 
project and track messages that have not been translated, or are missing, from supported locales. By doing this, the 
utility is capable of exporting these messages in predefined formats so that they can be provided to translations 
services, and later import the corresponding translations when these come back.

To track message bundles, the utility as a minimum needs:
* Default Locale - The locale to be used as the default one. All bundle resources with this locale will be treated as 
the source for translations.
* Supported Locales - All locales the software project supports.
* Sources: Where to look for message bundles. 

# Setup
This utility runs on Python 3, so as a pre-requisite, Pythonh 3 and PIP 3 must be installed in your development 
environment, or wherever you plan to run this utility.

To install and make the utility accessible in the environment, run the following command in the root path of this 
project:
* `pip3 install .`
* Test by running: `translator version`    

This utility requires the definition of a configuration file, that should be initialized at any path of your project 
where message bundles will be tracked. To simplify the creation of this, the utility provides a mechanism to initiate 
one by defining the minimal inputs. The initially created config file can be modified with more specific configuration.

`$ translator init -l en_US -s .`

where:
* `init`: Command to initialize your config file
* `-l` or `--source-locale`: The locale of the resources to track (this would be the default locale)
* `-s` or `--source-path`: List of relative paths from where to look for message bundles to track

For every message bundle found, a `snapshot` file will be created based on the resource for the provided source locale. 
The `snapshot` file is the file used by the utility to track message updates or additions. An initial run will assume
that the current state of the default resource as the starting point. From this moment on, the `snapshot` will not be 
modified by the utility, unless updated translations are imported. 

The `init` command will display a list of the bundles found, and display the information for these, including the 
created `snapshot` file. If fopr some reason these are not the ones you want to include, you can revert them by running
a `clean` command using the same parameters used for the `init`:

`$ translator clean -l en_US -s .` 

This can be run at any time, if for some reason you want to clean the `snapshots`.

The `init` command will create a simple configuration file like such:
```yaml
locales:
  default: en_US
  supported:
  - fr_CA
  - ja
  - es
  - it
  - fr_FR
  - zh_HK
  - zh_CN
  - ar
  - de
sources:
- .
```

The configuration file follows the following format:
```yaml
locales:
  default: <source_locale>
  supported:
  - <locale>
  - ...
sources:
  - <relative_path/to/message_bundles/sources>
  - ...
```
where each entry under `sources` corresponds to list of relative paths where the utility will search for message 
bundles.

* Run `translator view` to display a status of translations based on the config file provided. This display would show 
messages that are new (have not been translated), and any missing translations from any supported locale.
