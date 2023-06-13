"""
File for handling atk files.
Meta: Metadata for the atk
  Name: str
  Author: str
  Version: str the version of this atk
  ProgramVersion: str the version of the program that made the atk
Script: What to execute.
  Section
    Name: str Name of section for readability.
    ID: int The real identifier.
    Type: ScriptSectionType How to handle content(Embedded or Reference)
    Content: str
  Requires: [str] List of executables needed to run the script.
Output: Output of each Script section(optional)
  Section
    ID: int
    Content: str
Document: How to generate the document.
  Section
    Name: str Name of section, for readability.
    ID: str The real identifier.
    Type: DocumentSectionType How to handle content(of section)
    Content: str
    Pattern: Patterns for setting content from output.
      pattern_str: str The regex pattern to match.
      match_content: str the content to use if matched.
Variables: dict Key Value pairs to pass into script sections.
  If there is a key with no value("") then ask user for this.
"""
import typing
# from typing_extensions import Self
import json
from enum import Enum


class SectionBase:
    def __init__(self, section_id: int, content: str):
        self.section_id = section_id
        self.content = content

    def to_dict(self) -> dict:
        return {
            "id": self.section_id,
            "content": self.content
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict())

    @classmethod
    def from_dict(cls, in_dict: dict):
        return cls(in_dict["id"], in_dict["content"])

    @classmethod
    def from_json(cls, json_str: str):
        return cls.from_dict(json.loads(json_str))


class ScriptSectionType(Enum):
    EMPTY = "Empty"
    EMBEDDED = "Embedded"
    REFERENCE = "Reference"


class SectionScript(SectionBase):
    def __init__(self, section_id: int, name: str, section_type: ScriptSectionType, content: str):
        super().__init__(section_id, content)
        self.name = name
        self.section_type = section_type

    def to_dict(self) -> dict:
        return super().to_dict() | {"name": self.name, "type": self.section_type.value}

    @classmethod
    def from_dict(cls, in_dict: dict):
        return cls(in_dict["id"], in_dict["name"], ScriptSectionType(in_dict["type"]), in_dict["content"])


class DocumentSectionType(Enum):
    EMPTY = "Empty"
    LITERAL = "Literal"
    REFERENCE = "Reference"
    PATTERN = "Pattern"
    COMBINED = "Combined"


class Pattern:
    def __init__(self, pattern_str: str, match_content: str):
        self.pattern_str = pattern_str
        self.match_content = match_content

    def to_dict(self) -> dict:
        return {"pattern": self.pattern_str, "match_content": self.match_content}

    def to_json(self) -> str:
        return json.dumps(self.to_dict())

    @classmethod
    def from_dict(cls, in_dict):
        return cls(in_dict["pattern"], in_dict["match_content"])

    @classmethod
    def from_json(cls, json_str):
        return cls.from_dict(json.loads(json_str))


class SectionDocument(SectionBase):
    def __init__(self, section_id: int, name: str, section_type: DocumentSectionType, content: str,
                 patterns: list[Pattern]):
        super().__init__(section_id, content)
        self.name = name
        self.section_type = section_type
        self.patterns = patterns

    def to_dict(self) -> dict:
        patterns = []
        for pattern in self.patterns:
            patterns.append(pattern.to_dict())
        return super().to_dict() | {"name": self.name, "type": self.section_type.value, "patterns": patterns}

    @classmethod
    def from_dict(cls, in_dict: dict):
        patterns = []
        for pattern_dict in in_dict["patterns"]:
            patterns.append(Pattern.from_dict(pattern_dict))
        return cls(in_dict["id"], in_dict["name"], DocumentSectionType(in_dict["type"]), in_dict["content"], patterns)


class Meta:
    def __init__(self, name: str, author: str, version: str = "0.0.0", program_version: str = "0.0.0"):
        self.name = name
        self.author = author
        self.version = version
        self.program_version = program_version

    def to_dict(self):
        return {
            "meta": {
                "name": self.name,
                "author": self.author,
                "version": self.version,
                "program_version": self.program_version
            }
        }

    def to_json(self):
        return json.dumps(self.to_dict())

    @classmethod
    def from_dict(cls, in_dict: dict):
        return cls(in_dict["meta"]["name"], in_dict["meta"]["author"], in_dict["meta"]["version"],
                   in_dict["meta"]["program_version"])

    @classmethod
    def from_json(cls, json_str: str):
        return cls.from_dict(json.loads(json_str))


class Script:
    def __init__(self, sections: list, requires: list[str]):
        self.sections = sections
        self.requires = requires

    def to_dict(self):
        dict_sections = []
        for section in self.sections:
            dict_sections.append(section.to_dict())
        return {"script": {"sections": dict_sections, "requires": self.requires}}

    def to_json(self):
        return json.dumps(self.to_dict())

    @classmethod
    def from_dict(cls, in_dict: dict):
        imported_sections = []
        for section in in_dict["script"]["sections"]:
            imported_sections.append(SectionScript.from_dict(section))
        return cls(imported_sections, in_dict["script"]["requires"])

    @classmethod
    def from_json(cls, json_str: str):
        return cls.from_dict(json.loads(json_str))


class Output:
    def __init__(self, sections: list[SectionBase]):
        self.sections = sections

    def to_dict(self):
        dict_sections = []
        for section in self.sections:
            dict_sections.append(section.to_dict())
        return {"output": {"sections": dict_sections}}

    def to_json(self):
        return json.dumps(self.to_dict())

    @classmethod
    def from_dict(cls, in_dict: dict):
        imported_sections = []
        for section in in_dict["output"]["sections"]:
            imported_sections.append(SectionBase.from_dict(section))
        return cls(imported_sections)

    @classmethod
    def from_json(cls, json_str: str):
        return cls.from_dict(json.loads(json_str))


class Document:
    def __init__(self, sections: list[SectionDocument]):
        self.sections = sections

    def to_dict(self) -> dict:
        dict_sections = []
        for section in self.sections:
            dict_sections.append(section.to_dict())
        return {"document": {"sections": dict_sections}}

    def to_json(self) -> str:
        return json.dumps(self.to_dict())

    @classmethod
    def from_dict(cls, in_dict: dict):
        imported_sections = []
        for section in in_dict["document"]["sections"]:
            imported_sections.append(SectionDocument.from_dict(section))
        return cls(imported_sections)

    @classmethod
    def from_json(cls, json_str: str):
        return cls.from_dict(json.loads(json_str))


class Attack:
    def __init__(self, meta: Meta, script: Script, document: Document, variables: dict, output: Output = None):
        self.meta = meta
        self.script = script
        self.output = output
        self.document = document
        self.variables = variables

    def to_dict(self):
        final = {} | self.meta.to_dict() | self.script.to_dict() | self.document.to_dict() | {
            "variables": self.variables}
        if self.output is not None:
            final = final | self.output.to_dict()
        return final

    def to_json(self):
        return json.dumps(self.to_dict())

    def save(self, path: str) -> None:
        with open(path, "w") as f:
            f.write(self.to_json())

    @classmethod
    def from_dict(cls, in_dict: dict):
        output = None
        try:
            output = {"output": in_dict["output"]}
        except KeyError:
            pass
        if output is None:
            return cls(
                Meta.from_dict({"meta": in_dict["meta"]}),
                Script.from_dict({"script": in_dict["script"]}),
                Document.from_dict({"document": in_dict["document"]}),
                in_dict["variables"]
            )
        else:
            return cls(
                Meta.from_dict({"meta": in_dict["meta"]}),
                Script.from_dict({"script": in_dict["script"]}),
                Document.from_dict({"document": in_dict["document"]}),
                in_dict["variables"],
                Output.from_dict(output)
            )

    @classmethod
    def from_json(cls, json_str: str):
        return cls.from_dict(json.loads(json_str))

    @classmethod
    def load(cls, path: str):
        with open(path, "r") as f:
            return cls.from_json(f.read())


if __name__ == "__main__":
    # For testing
    attack_obj_from_file = Attack.load("tmp.atk")
    attack_obj_from_file.save("tmp1.atk")
    print("done")
