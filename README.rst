django-puppeteer-pdf
==================

.. image:: https://badge.fury.io/py/django-puppeteer-pdf.png
    :target: http://badge.fury.io/py/django-puppeteer-pdf
    :alt: Latest version

.. image:: https://travis-ci.org/namespace-ee/django-puppeteer-pdf.png?branch=master
   :target: https://travis-ci.org/namespace-ee/django-puppeteer-pdf
   :alt: Travis-CI

.. image:: https://readthedocs.org/projects/django-puppeteer-pdf/badge/?version=latest
    :target: http://django-puppeteer-pdf.readthedocs.io/en/latest/?badge=latest
    :alt: Documentation Status

.. image:: https://img.shields.io/pypi/dm/django-puppeteer-pdf.svg
    :target: https://badge.fury.io/py/django-puppeteer-pdf
    :alt: Number of PyPI downloads on a month


Converts HTML to PDF
--------------------

Provides Django views to wrap the HTML to PDF conversion using `puppeteer <https://github.com/GoogleChrome/puppeteer>`_.

Forked from: `django-wkhtmltopdf <https://github.com/incuna/django-wkhtmltopdf>`_.

Requirements
------------

cli for puppeteer `puppeteer-pdf <https://www.npmjs.com/package/puppeteer-pdf>`_.

Python 2.6+ and 3.3+ are supported.
See travis-ci build status for details


Note
------------

* Current version is only tested as a use of django rest framework renderer `examples/drf_renderer.py`
* Documentation is not up to date but you can see working use cases in `examples` directory
* Reporting bugs and issues is welcomed

Installation
------------

Run ``pip install django-puppeteer-pdf``.

By default it will execute the first ``puppeteer-pdf`` command found on your ``PATH``.

It is recommended to specify full path of puppeteer-pdf using one of the way mentioned below.

If you can't add puppeteer-pdf to your ``PATH``, you can set ``PUPPETEER_PDF_CMD`` to a
specific executable:

e.g. in ``settings.py``: ::

    PUPPETEER_PDF_CMD = '/path/to/my/puppeteer-pdf'

or alternatively as env variable: ::

    export PUPPETEER_PDF_CMD=/path/to/my/puppeteer-pdf

You may also set ``PUPPETEER_PDF_CMD_OPTIONS`` in ``settings.py`` to a dictionary
of default command-line options.

The default is: ::

    PUPPETEER_PDF_CMD_OPTIONS = {
        'format': 'A4',
    }

Documentation
-------------

Documentation is available at http://django-puppeteer-pdf.readthedocs.org/en/latest/.

License
-------

MIT licensed. See the bundled `LICENSE <https://github.com/namespace/django-puppeteer-pdf/blob/master/LICENSE>`_ file for more details.
