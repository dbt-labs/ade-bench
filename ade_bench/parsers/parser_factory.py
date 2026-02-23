from enum import Enum

from ade_bench.parsers.base_parser import BaseParser
from ade_bench.parsers.dbt_parser import DbtParser
from ade_bench.parsers.claude_parser import ClaudeParser
from ade_bench.parsers.macro_parser import MacroParser


class ParserName(Enum):
    DBT = "dbt"
    DBT_FUSION = "dbt-fusion"
    CLAUDE = "claude"
    MACRO = "macro"


class ParserFactory:
    PARSER_NAME_TO_CLASS = {
        ParserName.DBT: DbtParser,
        ParserName.DBT_FUSION: DbtParser,  # dbt-fusion uses the same parser as dbt
        ParserName.CLAUDE: ClaudeParser,
        ParserName.MACRO: MacroParser,
    }

    @staticmethod
    def get_parser(parser_name: ParserName | str, **kwargs) -> BaseParser:
        # Convert string to ParserName if needed
        if isinstance(parser_name, str):
            try:
                parser_name = ParserName(parser_name)
            except ValueError:
                raise ValueError(
                    f"Unknown parser: {parser_name}. Available parsers: {[p.value for p in ParserName]}"
                )

        parser_class = ParserFactory.PARSER_NAME_TO_CLASS.get(parser_name)
        if not parser_class:
            raise ValueError(
                f"Unknown parser: {parser_name}. "
                f"Available parsers: {ParserFactory.PARSER_NAME_TO_CLASS.keys()}"
            )

        # For DbtParser, pass the parser type based on the parser name
        if parser_class == DbtParser:
            parser_type = parser_name.value  # "dbt" or "dbt-fusion"
            return parser_class(parser_type=parser_type, **kwargs)

        return parser_class(**kwargs)
