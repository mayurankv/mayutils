import re
import sys


MODULE_REGEX = r"^[_a-zA-Z][_a-zA-Z0-9]+$"

project_name = "{{ cookiecutter.project_name }}"

if project_name.strip() == "":
    print("ERROR: project_name cannot be empty")

    sys.exit(1)

project_short_description = "{{ cookiecutter.project_short_description }}"

if project_short_description.strip() == "":
    print("ERROR: project_short_description cannot be empty")

    sys.exit(1)

package_name = "{{ cookiecutter.package_name }}"

if not re.match(pattern=MODULE_REGEX, string=package_name):
    print(f"ERROR: {package_name} is not a valid Python package name")

    sys.exit(1)
