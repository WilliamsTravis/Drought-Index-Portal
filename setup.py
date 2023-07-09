"""Setup for drip package installation.

Note:
    - Please confirm that GDAL is installed on your system or run
      `install_gdal.sh` before installating this package.
    - If you are having problems with the Python GDAL package, try installing
      with the `--no-cache-dir` option.
"""
import os
import subprocess as sp

from setuptools import setup


os.environ["CPLUS_INCLUDE_PATH"] = "/usr/include/gdal"
os.environ["C_INCLUDE_PATH"] = "/usr/include/gdal"


def get_gdal_version():
    """Return system GDAL version."""
    process = sp.Popen(
        ["gdal-config", "--version"],
        stdout=sp.PIPE,
        stderr=sp.PIPE
    )
    sto, ste = process.communicate()
    if ste:
        raise OSError("GDAL is causing problems again. Make sure you can run "
                      "'gdal-config --version' successfully in your terminal")
    version = sto.decode().replace("\n", "")
    return version


def get_requirements():
    """Get requirements and update gdal version number."""
    with open("requirements.txt", encoding="utf-8") as file:
        reqs = file.readlines()
    gdal_version = get_gdal_version()
    gdal_line = [req for req in reqs if req.startswith("gdal")][0]
    gdal_line = gdal_line[:-1]
    reqs = [req for req in reqs if not req.startswith("gdal")]
    gdal_line = f"{gdal_line}=={gdal_version}\n"
    reqs.append(gdal_line)
    return reqs


setup(
    name="drip",
    packages=["drip"],
    version="0.2.0",
    author="Travis Williams",
    author_email="twillico@proton.me",
    include_package_data=True,
    install_requires=get_requirements(),
    python_requires=">=3.9",
    test_suite="tests",
    package_data={
        "data": [
           "*"
        ]
    }
)
