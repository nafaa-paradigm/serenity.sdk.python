## Serenity SDK - Python

### Introduction

The Serenity digital asset risk platform exposes all functionality via an API -- currently REST only.

Although it's possible to call the API with simple HTTP client code in most any modern language, there are conventions that need to be followed -- especially for authentication and authorization -- and to make it easier we have provided this lightweight SDK.

### Installation

Installation for Python 3.x users is very simple using pip:

```plain
pip install serenity.sdk.python
```

If you have already installed the SDK and want to upgrade to latest:

```plain
pip install -U serenity.sdk.python
```

### API documentation

The latest API documentation is always available at [ReadTheDocs](https://serenitysdkpython.readthedocs.io/en/stable/).

### Maintainer setup

If you are checking in code for ```serenity.sdk.python``` you may wish to run ```setup.sh``` to install appropriate pre-commit and pre-push git hooks in your local repo. Once you run setup you will also get a Python virtual environment in ```.venv``` generated by Poetry; if using VSCode, you should select this as your IDE's virtual environment.

### Learning more

If you want to learn more about the Serenity digital asset risk platform, book a demo or get in touch, you can reach out to us at [https://cloudwall.tech](https://cloudwall.tech).