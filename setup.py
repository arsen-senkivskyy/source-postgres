from distutils.core import setup

setup(
    name="panoply_postgres",
    version="2.3.7",
    description="Panoply Data Source for Postgres",
    author="Panoply Dev Team",
    author_email="support@panoply.io",
    url="http://panoply.io",
    install_requires=[
        "panoply-python-sdk==1.6.0",
        "psycopg2==2.7.1",
        "backoff==1.4.3"
    ],
    extras_require={
        "test": [
            "pycodestyle==2.5.0",
            "coverage==4.3.4",
            "mock==2.0.0"
        ]
    },

    # place this package within the panoply package namespace
    package_dir={"panoply": ""},
    packages=["panoply.postgres"]
)
