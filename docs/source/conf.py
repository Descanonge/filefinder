# Configuration file for the Sphinx documentation builder.
#
# This file only contains a selection of the most common options. For a full
# list see the documentation:
# https://www.sphinx-doc.org/en/master/usage/configuration.html

# -- Path setup --------------------------------------------------------------

# If extensions (or modules to document with autodoc) are in another directory,
# add these directories to sys.path here. If the directory is relative to the
# documentation root, use os.path.abspath to make it absolute, like shown here.
# import os
# import sys
import filefinder

# -- Project information -----------------------------------------------------

project = "filefinder"
copyright = "2021, Clément Haëck"
author = "Clément Haëck"

# The full version, including alpha/beta/rc tags
release = filefinder.__version__
version = filefinder.__version__
print(f"filefinder: {version}")

master_doc = "index"
templates_path = ["_templates"]
exclude_patterns = ["_build"]

# -- General configuration ---------------------------------------------------

# Add any Sphinx extension module names here, as strings. They can be
# extensions coming with Sphinx (named 'sphinx.ext.*') or your custom
# ones.
extensions = [
    "sphinx.ext.napoleon",
    "sphinx.ext.autosectionlabel",
    "sphinx.ext.autodoc",
    "sphinx.ext.autosummary",
    "sphinx.ext.intersphinx",
]

# Napoleon config
napoleon_google_docstring = False
napoleon_numpy_docstring = True
napoleon_use_param = True
napoleon_use_rtype = False
napoleon_preprocess_type = False

add_module_names = False

# Autosummary config
autosummary_generate = ["api.rst"]

# Autodoc config
autodoc_typehints = "description"
autodoc_typehints_format = "short"

# Intersphinx config
intersphinx_mapping = {
    "python": ("https://docs.python.org/3/", None),
    "numpy": ("https://numpy.org/doc/stable", None),
    "dask": ("https://docs.dask.org/en/latest", None),
    "xarray": ("https://docs.xarray.dev/en/stable/", None),
}

# -- Options for HTML output -------------------------------------------------

# The theme to use for HTML and HTML Help pages.  See the documentation for
# a list of builtin themes.
#
html_theme = "sphinx_book_theme"
html_static_path = ["_static"]
html_css_files = ["css/custom.css"]
html_title = "heterogeneity-index"
html_theme_options = dict(
    collapse_navigation=False,
    use_download_button=True,
    use_fullscreen_button=False,
    # TOC
    show_toc_level=2,
    # Link to source in repo
    repository_url="https://github.com/Descanonge/filefinder",
    use_source_button=True,
    repository_branch="master",
    path_to_docs="doc",
    # Social icons
    icon_links=[
        dict(
            name="Repository",
            url="https://github.com/Descanonge/filefinder",
            icon="fa-brands fa-square-github",
        ),
        dict(
            name="Documentation",
            url="https://filefinder.readthedocs.io",
            icon="fa-solid fa-book",
        ),
    ],
    # Footer
    article_footer_items=["prev-next"],
    content_footer_items=[],
    footer_start=["footer-left"],
    footer_end=["footer-right"],
)
html_last_updated_fmt = "%Y-%m-%d"

html_sidebars = {"**": ["navbar-logo.html", "sbt-sidebar-nav.html", "icon-links.html"]}

# Add any paths that contain custom static files (such as style sheets) here,
# relative to this directory. They are copied after the builtin static files,
# so a file named "default.css" will overwrite the builtin "default.css".
html_static_path = []
