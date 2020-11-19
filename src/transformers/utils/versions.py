"""
Utilities for working with package versions
"""

import operator
import re
import sys

from packaging import version

import pkg_resources


ops = {
    "<": operator.lt,
    "<=": operator.le,
    "==": operator.eq,
    "!=": operator.ne,
    ">=": operator.ge,
    ">": operator.gt,
}


def require_version(requirement, hint=None):
    """
    Perform a runtime check of the dependency versions, using the exact same syntax used by pip.

    The installed module version comes from the `site-packages` dir via `pkg_resources`.

    Args:
    - requirement: pip style definition, e.g.,  "tokenizers==0.9.4", "tqdm>=4.27",
    - hint: what suggestion to print in case of requirements not being met
    """

    # note: while pkg_resources.require_version(requirement) is a much simpler way to do it, it
    # fails if some of the dependencies of the dependencies are not matching, which is not necessarily
    # bad, hence the more complicated check - which also should be faster, since it doesn't check
    # dependencies of dependencies.

    match = re.findall(r"^([^\!=<>\s]+)([\s\!=<>]{1,2})(.+)", requirement)
    if not match:
        raise ValueError(
            f"requirement needs to be in the pip package format, .e.g., package_a==1.23, or package_b>=1.23, but got {requirement}"
        )
    pkg, op, want_ver = match[0]
    if op not in ops:
        raise ValueError(f"need one of {list(ops.keys())}, but got {op}")

    # special case
    if pkg == "python":
        got_ver = ".".join([str(x) for x in sys.version_info[:3]])
        if not ops[op](version.parse(got_ver), version.parse(want_ver)):
            raise pkg_resources.VersionConflict(
                f"{requirement} is required for a normal functioning of this module, but found {pkg}=={got_ver}."
            )
        return

    try:
        got_ver = pkg_resources.get_distribution(pkg).version
    except pkg_resources.DistributionNotFound:
        raise pkg_resources.DistributionNotFound(
            f"{requirement} is required for a normal functioning of this module, but it is not installed. "
            + ("\n" + hint if hint is not None else ""),
            requirement,
        )

    if not ops[op](version.parse(got_ver), version.parse(want_ver)):
        raise pkg_resources.VersionConflict(
            f"{requirement} is required for a normal functioning of this module, but found {pkg}=={got_ver}. "
            + "\n"
            + hint
            if hint is not None
            else ""
        )


def require_version_core(requirement):
    """ require_version wrapper which emits a core-specific hint on failure """
    hint = "Try: pip install transformers -U or pip install -e '.[dev]' if you're working with git master"
    return require_version(requirement, hint)


def require_version_examples(requirement):
    """ require_version wrapper which emits examples-specific hint on failure """
    hint = "Try: pip install -r examples/requirements.txt"
    return require_version(requirement, hint)
