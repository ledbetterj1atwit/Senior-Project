import pylatex
from sys import argv
import re

from App.attack import Attack, SectionDocument, DocumentSectionType, Pattern, PatternBehavior


class EndDocumentException(Exception):
    def __init__(self, message="Document generation is ending early. Likely due to a pattern with END behavior."):
        self.message = message


class PatternErrorException(Exception):
    def __init__(self,
                 message="Document generation failed because an ERROR pattern matched, check your attack output."):
        self.message = message


def get_matching_patterns(atk: Attack, doc_section_id: int) -> list[Pattern]:
    output_section = None
    doc_section = None
    matching = []
    for o_s in atk.output.sections:
        if o_s.section_id == doc_section_id:
            output_section = o_s
            break
    for d_s in atk.document.sections:
        if d_s.section_id == doc_section_id:
            doc_section = d_s
            break
    for pattern in doc_section.patterns:
        if re.match(pattern.pattern_str, output_section.content):
            matching.append(pattern)
    return matching


def create_section(doc: pylatex.Document, atk: Attack, document_section_id: int):
    section = None
    remove_section = False
    for d_s in atk.document.sections:
        if d_s.section_id == document_section_id:
            section = d_s
            break
    with doc.create(pylatex.Section(section.name)):
        if section.section_type == DocumentSectionType.REFERENCE:
            with open(section.content, "r") as f:
                doc.append(f.read())
        elif section.section_type == DocumentSectionType.LITERAL:
            doc.append(section.content)
        elif section.section_type == DocumentSectionType.PATTERN:
            matching = get_matching_patterns(atk, document_section_id)
            print(matching)
            to_add = str(section.content)  # I want a copy of the content string.
            for match in matching:
                if match.behavior is PatternBehavior.ADD:
                    to_add += match.match_content
                elif match.behavior is PatternBehavior.REPLACE:
                    to_add = match.match_content
                elif match.behavior is PatternBehavior.REMOVE:
                    remove_section = True
                elif match.behavior is PatternBehavior.END:
                    raise EndDocumentException()
                elif match.behavior is PatternBehavior.ERROR:
                    raise PatternErrorException()
            doc.append(to_add)
        elif section.section_type is DocumentSectionType.COMBINED:
            pass  # This one is complicated, might work on it later.
    if remove_section:
        doc.pop(-1)


def create_section_preview(atk: Attack, section_id: int, path: str):
    document = pylatex.Document()
    create_section(document, atk, section_id)
    document.generate_pdf(path, clean_tex=True)


def create_report(atk: Attack, path: str):
    document = pylatex.Document()
    for section in atk.document.sections:
        create_section(document, atk, section.section_id)
    document.generate_pdf(path, clean_tex=True)


if __name__ == "__main__":
    path = "doc_gen.pdf"
    attack_path = "../gen.atk"
    try:
        path = argv[1]
    except IndexError:
        pass
    document = pylatex.Document()
    atk = Attack.load(attack_path)
    for idx in range(1, len(atk.document.sections) + 1):
        create_section(document, atk, idx)

    document.generate_pdf(path, clean_tex=False)
