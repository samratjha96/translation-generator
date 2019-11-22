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
* Create a file called `translation-config.yml` in the root of your repository that you want to use this tool on
* The `translation-config.yml` file should look like this:
```yaml
bundles:
  - path: <path/to/your/bundle>
    extension: <properties | json>
    default_locale: <locale_key> # optional key. Defaults to en_US if not provided
```
where each entry under `bundles` corresponds to a resource bundle that you want to manage with this tool
* Run `translator --generate` to begin using the tool

# Enhancements
* Everywhere snapshot_file is referred to, should probably change to snapshot_file_name because that's what the bundle object returns
* The reconciliator assumes order of insertion into a dictionary is preserved. When the processor parses all the files and converts them to a dictionary representation, the reconciliator assumes that this was done in order. Key value pairs in the dictionary representation outputted by the processor should appear in the same order they originally show up in the file
* Rename the tool to not be so boring :D
* Parallelize all the bundle operations. Can use threads or asyncio for this
