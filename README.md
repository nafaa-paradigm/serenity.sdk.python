## Serenity SDK - Python

### Introduction

The Serenity digital asset risk platform exposes all functionality via an API -- currently REST only.

Although it's possible to call the API with simple HTTP client code in most any modern language, there
are conventions that need to be followed -- especially for authentication and authorization -- and to
make it easier we have provided this lightweight SDK.

### Installation

Installation for Python 3.x users is very simple using pip:

```plain
pip install serenity.sdk.python
```

### Building locally

If you wish to run the local setup you can use the provided ```Makefile```, however this
is primarily aimed for internal Cloudwall use; we recommend clients use pip install.

```bash
# set up a virtual environment with dependencies
make venv

# check code
make link

# run tests
make test

# publish latest code to PyPi (token required)
make publish

# clean up
make clean
```

### Learning more

At this time the API and its documentation are only available to members of our private beta, via
their personal Serenity Developer Portal, e.g. https://developer.$client.cloudwall.network.