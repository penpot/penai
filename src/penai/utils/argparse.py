import argparse

from jsonargparse import ArgumentParser
from jsonargparse._common import parser_context
from jsonargparse._namespace import patch_namespace
from jsonargparse._typehints import ActionTypeHint
from overrides import override


class HandleFlagsArgumentParser(ArgumentParser):
    """Changes the argument parsing such that kwargs with default value of False are interpreted as flags by `CLI`."""

    # Note: type ignore is needed for some reason even though the source code has no annotations
    # Mypy reads the correct type of the baseclass from somewhere, apparently even with an @overload
    # I don't understand where it is declared though
    @override
    def parse_known_args(  # type: ignore[override]
        self,
        args: list[str],
        namespace: argparse.Namespace,
    ) -> tuple[argparse.Namespace, list[str]]:
        # Had to copy the code from the parent class because of the way the parent class is implemented
        # Can't call super().parse_known_args()
        # This implementation omits the caller-dependent args-completion logic
        if namespace is not None and args is not None:
            args_with_boolean_flags = []
            for arg in args:
                args_with_boolean_flags.append(arg)
                if arg.startswith("--") and "=" not in arg and namespace[arg[2:]] is False:  # type: ignore[index]
                    # We encountered a boolean flag that was False by default. Interpreted as user setting it to True
                    args_with_boolean_flags.append("True")
            args = args_with_boolean_flags

        try:
            with patch_namespace(), parser_context(
                parent_parser=self,
                lenient_check=True,
            ), ActionTypeHint.subclass_arg_context(self):
                namespace, args = self._parse_known_args(args, namespace)
        except argparse.ArgumentError as ex:
            self.error(str(ex), ex)

        return namespace, args
