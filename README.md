# Overview
This tool is designed to fix the pain of developing in one locale but having to have corresponding entries for newly added strings in all supported locales

# Setup
* Make sure you have `virtualenv` installed
    * Run `pip3 install virtualenv` if you don't already have it
* Run `virtualenv translation`
* Run `source translation/bin/activate` to activate this virtual environment
* Run `pip install -r requirements.txt` to configure all the dependencies
* Run `chmod +x translator` and then `sudo cp -r translator /usr/local/bin/translator` to be able to invoke the tool from anywhere

# Usage
* Create a file called `translation-config.yml` in the root of your repository that you want to use this tool on. Or alternatively, create a default one by running the command:
    * `translator init -l <source_locale> -s <list_of_source_paths>`
        * `source_locale`: The locale for all source files
        * `list_of_source_paths`: List of path where the process will look for source files. This argument accepts multiple entries separated by space, and also wild cards such as `./some_path/**/resources` 
* The `translation-config.yml` file should look like this:
```yaml
locales:
  default: <source_locale>
  supported:
  - <locale>
  - ...
bundles:
  - source: <path/to/a/source/resource>
  - ...
```
where each entry under `bundles` corresponds to a resource bundle that you want to manage with this tool
* Run `translator view` to display a status of translations based on the config file provided. This display would show messages that are new (have not been translated), and any missing translations from any supported locale.
