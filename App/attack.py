"""
Meta
  Name: str
  Author: str
  Version: str
  ProgramVersion: str
Script
  Section
    Name: str
    ID: int
    Type: str
    Content: str
  Requires: [str]
Output
  Section
    ID: int
    Content: str
Document
  Section
    Name: str
    ID: str
    Type: str
    Content: str
"""
import typing
# from typing_extensions import Self
import json


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


class SectionScript(SectionBase):
    def __init__(self, section_id: int, name: str, section_type: str, content: str):
        super().__init__(section_id, content)
        self.name = name
        self.section_type = section_type

    def to_dict(self) -> dict:
        return super().to_dict() | {"name": self.name, "type": self.section_type}

    @classmethod
    def from_dict(cls, in_dict: dict):
        return cls(in_dict["id"], in_dict["name"], in_dict["type"], in_dict["content"])


class SectionDocument(SectionBase):
    def __init__(self, section_id: int, name: str, section_type: str, content: str):
        super().__init__(section_id, content)
        self.name = name
        self.section_type = section_type

    def to_dict(self) -> dict:
        return super().to_dict() | {"name": self.name, "type": self.section_type}

    @classmethod
    def from_dict(cls, in_dict: dict):
        return cls(in_dict["id"], in_dict["name"], in_dict["type"], in_dict["content"])


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
        return cls(in_dict["meta"]["name"], in_dict["meta"]["author"], in_dict["meta"]["version"], in_dict["meta"]["program_version"])

    @classmethod
    def from_json(cls, json_str: str):
        return cls.from_dict(json.loads(json_str))


class Attack:
    def __init__(self, meta: Meta, script: Script, document: Document, output: Output = None):
        self.meta = meta
        self.script = script
        self.output = output
        self.document = document

    def to_dict(self):
        final = {} | self.meta.to_dict() | self.script.to_dict() | self.document.to_dict()
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
                Document.from_dict({"document": in_dict["document"]})
            )
        else:
            return cls(
                Meta.from_dict({"meta": in_dict["meta"]}),
                Script.from_dict({"script": in_dict["script"]}),
                Document.from_dict({"document": in_dict["document"]}),
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
    print("done")
