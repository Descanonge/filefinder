# Configuration file for the Sphinx documentation builder.
#
# For the full list of built-in configuration values, see the documentation:
# https://www.sphinx-doc.org/en/master/usage/configuration.html

from sphinx.application import Sphinx

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
    "sphinx_design",
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
    "private-members": False,
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

html_theme = "pydata_sphinx_theme"
# html_static_path = ["_static"]
html_title = "FileFinder"
html_theme_options = dict(
    collapse_navigation=False,
    show_toc_level=2,
    # Social icons
    icon_links=[
        dict(
            name="Repository",
            url="https://github.com/Descanonge/filefinder",
            icon="fa-brands fa-github",
        ),
        dict(
            name="PyPI",
            url="https://pypi.org/project/filefinder",
            icon="fa-brands fa-python",
        ),
    ],
    # Navbar
    navbar_start=["navbar-logo"],
    navbar_center=["spacer"],
    navbar_end=["search-button", "theme-switcher", "navbar-icon-links"],
    # Footer
    show_prev_next=False,
    article_footer_items=[],
    content_footer_items=[],
    footer_start=["copyright", "last-updated"],
    footer_end=["sphinx-version", "theme-version"],
)
html_last_updated_fmt = "%Y-%m-%d"

html_sidebars = {"**": ["sidebar-nav.html"]}


def remove_none_return_type(
    app: Sphinx,
    obj_type: str,
    name: str,
    obj: Any,
    options,
    signature: str,
    return_annotation: str,
) -> tuple[str, str]:
    print(name, signature, return_annotation)
    if return_annotation == "None":
        return_annotation = ""
    return signature, return_annotation


def setup(app: Sphinx) -> dict:
    app.connect("autodoc-process-signature", remove_none_return_type)

    return {
        "parallel_read_safe": True,
        "parallel_write_safe": True,
    }
