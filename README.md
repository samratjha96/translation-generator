# Overview
This tool is designed to fix the pain of developing in one locale but having to have corresponding entries for newly added strings in all supported locales

# Setup
* Make sure you have `virtualenv` installed
    * Run `pip3 install virtualenv` if you don't already have it
* Run `virtualenv translation`
* Run `source translation/bin/activate` to activate this virtual environment
* Run `pip install -r requirements.txt` to configure all the dependencies

# Usage
* Create a file called `translation-config.yml` in the root of your repository that you want to use this tool on
* The `translation-config.yml` file should look like this:
```yaml
bundles:
  - path: <path/to/your/bundle>
    extension: <properties | json>
    default_locale: <locale_key> # optional key. Defaults to en_US if not provided
```
where each entry under `bundles` corresponds to a resource bundle that you want to manage with this tool
* Run `python3 translator.py --generate` to begin using the tool
