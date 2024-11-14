# Configuration file for the Sphinx documentation builder.
#
# For the full list of built-in configuration values, see the documentation:
# https://www.sphinx-doc.org/en/master/usage/configuration.html

import filefinder

## Project information

project = "Filefinder"
copyright = "2021, Clément Haëck"
author = "Clément Haëck"

release = filefinder.__version__
version = filefinder.__version__
print(f"filefinder: {version}")

## General configuration

templates_path = ["_templates"]
# exclude_patterns = []
pygments_style = "default"

nitpicky = True


extensions = [
    "sphinx.ext.intersphinx",
    "sphinx.ext.autodoc",
    "sphinx.ext.autosummary",
    "sphinx.ext.napoleon",
]

add_module_names = False
toc_object_entries_show_parents = "hide"

pygments_style = "default"

## Autodoc config
autodoc_typehints = "description"
autodoc_typehints_format = "short"
autodoc_typehints_description_target = "all"
# autodoc_member_order = "groupwise"
autodoc_class_content = "both"
autodoc_class_signature = "mixed"
autodoc_type_aliases = {
    "traitlets.traitlets.Int": "~traitlets.Int",
}

python_use_unqualified_type_names = True

autodoc_default_options = {
    "show-inheritance": True,
    "inherited-members": False,
    "private-members": True,
}
## Autosummary config
autosummary_generate = ["api.rst"]

## Napoleon config
napoleon_google_docstring = False
napoleon_numpy_docstring = True
napoleon_use_param = True
napoleon_use_rtype = False
napoleon_preprocess_type = False
# napoleon_type_aliases = autodoc_type_aliases.copy()

## Intersphinx config
intersphinx_mapping = {"python": ("https://docs.python.org/3/", None)}

## HTML Output

html_theme = "sphinx_book_theme"
# html_static_path = ["_static"]
html_title = "FileFinder"
html_theme_options = dict(
    collapse_navigation=False,
    use_download_button=True,
    use_fullscreen_button=False,
    show_toc_level=2,
    repository_url="https://github.com/Descanonge/filefinder",
    use_source_button=True,
    repository_branch="master",
    path_to_docs="doc",
    # Social icons
    icon_links=[
        dict(
            name="Repository",
            url="https://github.com/Descanonge/filefinder",
            icon="fa-brands fa-github",
        ),
        dict(
            name="PyPI",
            url="https://pypi.org/filefinder",
            icon="fa-brands fa-python",
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
