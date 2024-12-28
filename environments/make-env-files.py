# noqa: INP001
"""Make conda env.yml and pip requirements.txt files from environments.json data."""

from __future__ import annotations

import argparse
import itertools
import json
from pathlib import Path

import tomllib
from packaging.requirements import Requirement

# path to package's pyproject and the config json file
pyproject_path = "./pyproject.toml"
environments_config_path = "./environments/requirements/environments.json"

# what channels to specify in conda env yml files
CHANNELS = ["conda-forge"]

HEADER = (
    "# Do not edit this file. It is automatically generated by the script\n"
    "# environments/make-env-files.py using the environment definition data in\n"
    "# environments/environments.json and the requirements in pyproject.toml.\n"
)


def extract_optional_deps() -> list[Requirement]:
    """
    Extract a list of the optional dependencies/versions from pyproject.toml.

    Returns
    -------
    optional_deps
    """
    opts = pyproject["project"]["optional-dependencies"]
    return list({Requirement(o) for o in itertools.chain.from_iterable(opts.values())})


def make_requirement(
    requirement: Requirement,
    force_pin: bool = False,  # noqa: FBT001,FBT002
    is_conda: bool = True,  # noqa: FBT001,FBT002
) -> str:
    """
    Make a requirement specification string.

    The string result comprises the requirement's name and its specifier(s).

    Parameters
    ----------
    requirement
        A requirement object
    force_pin
        If True, pin requirement to version rather than using existing
        specifier. Allows you to convert minimum versions to pinned versions.
    is_conda
        If True and if `force_pin` is True, format the requirement string to
        end with ".*" for conda environment file pinning format compatibility.

    Returns
    -------
    requirement_str
    """
    specifiers = list(requirement.specifier)
    if force_pin and len(specifiers) == 1:
        spec = f"{requirement.name}=={specifiers[0].version}"
        if is_conda and not spec.endswith(".*"):
            spec += ".*"
        return spec
    return str(requirement)


def make_file(env_name: str) -> None:
    """
    Write a conda environment yaml file or pip requirements.txt file.

    Parameters
    ----------
    env_name
        An enviroment name among the keys of environments.json.

    Returns
    -------
    None
    """
    env = envs[env_name]

    # it's a conda env file if it ends with ".yml", otherwise it's a pip
    # requirements.txt file
    is_conda = env["output_path"].endswith(".yml")

    # determine which dependencies to add based on the configuration
    depends_on = []
    if env["needs_python"]:
        python_dep = Requirement(f"python{pyproject['project']['requires-python']}")
        depends_on.append(python_dep)
    if env["needs_dependencies"]:
        dependencies = [Requirement(d) for d in pyproject["project"]["dependencies"]]
        depends_on.extend(dependencies)
    if env["needs_optionals"]:
        optionals = extract_optional_deps()
        depends_on.extend(optionals)

    # make the list of requirements
    requirements = [
        make_requirement(dep, force_pin=env["force_pin"], is_conda=is_conda) for dep in depends_on
    ]

    # add any extra requirements if provided in the configuration
    if env["extras"] is not None:
        for extras_filepath in env["extras"]:
            with Path(extras_filepath).open() as f:
                requirements += f.read().splitlines()

    # convert the requirements to conda env yml or pip requirements.txt
    requirements = sorted(requirements)
    if not is_conda:
        text = HEADER + "\n".join(requirements) + "\n"
    else:
        data = {"name": env_name, "channels": CHANNELS, "dependencies": requirements}
        text = ""
        for k, v in data.items():
            if isinstance(v, list):
                text += k + ":\n  - " + "\n  - ".join(v) + "\n"
            elif isinstance(v, str):
                text += k + ": " + v + "\n"
        text = HEADER + text

    # write the file to disk
    with Path(env["output_path"]).open("w") as f:
        f.writelines(text)

    print(f"Wrote {len(requirements)} requirements to {env['output_path']!r}")  # noqa: T201


if __name__ == "__main__":
    # load the pyproject.toml and the environments.json config files
    with Path(pyproject_path).open("rb") as f:
        pyproject = tomllib.load(f)
    with Path(environments_config_path).open("rb") as f:
        envs = json.load(f)

    # parse any command-line arguments passed by the user
    arg_parser = argparse.ArgumentParser()
    arg_parser.add_argument("-n", dest="env_name", type=str)
    args = arg_parser.parse_args()

    if args.env_name is not None:
        # if user passed -n command line argument, generate only that file
        make_file(args.env_name)
    else:
        # otherwise, make all environment files
        for env_name in envs:
            make_file(env_name)
