# Configuration file for the Sphinx documentation builder.
#
# For the full list of built-in configuration values, see the documentation:
# https://www.sphinx-doc.org/en/master/usage/configuration.html

import filefinder

# -- Project information -----------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#project-information

project = "Filefinder"
copyright = "2021, Clément Haëck"
author = "Clément Haëck"

release = filefinder.__version__
version = filefinder.__version__
print(f"filefinder: {version}")

# -- General configuration ---------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#general-configuration

extensions = [
    "sphinx.ext.intersphinx",
    "sphinx.ext.autodoc",
    "sphinx.ext.autosummary",
    "sphinx.ext.napoleon",
]

templates_path = ["_templates"]
# exclude_patterns = []


# Napoleon config
napoleon_google_docstring = False
napoleon_numpy_docstring = True
napoleon_use_param = True
napoleon_use_rtype = False
napoleon_preprocess_type = False

pygments_style = "default"

# Document rtype in the 'returns' directive/section
# (get rtype from typehint)

add_module_names = False

# Autosummary config
autosummary_generate = ["api.rst"]

# Autodoc config
autodoc_typehints = "description"
autodoc_typehints_format = "short"
# autodoc_type_aliases = {
#     "xr.DataArray": "xarray.DataArray",
#     "xr.Dataset": "xarray.Dataset",
# }
# napoleon_type_aliases = autodoc_type_aliases.copy()

# Intersphinx config
intersphinx_mapping = {
    "python": ("https://docs.python.org/3/", None),
    "xarray": ("https://docs.xarray.dev/en/stable/", None),
}

# -- Options for HTML output -------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#options-for-html-output

html_theme = "sphinx_book_theme"
html_static_path = ["_static"]
html_title = "FileFinder"
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
            icon="fa-brands fa-square-gitlab",
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
