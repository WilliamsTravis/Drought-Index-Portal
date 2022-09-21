from setuptools import setup


# with open("requirements.txt") as f:
#     INSTALL_REQUIREMENTS = f.readlines()

setup(
    name="drip",
    packages=["drip"],
    version="0.1.0",
    author="Travis Williams",
    author_email="travissius@gmail.com",
    include_package_data=True,
    # install_requires=INSTALL_REQUIREMENTS,
    test_suite="tests",
    package_data={
        "data": [
           "*"
        ]
    }
)
