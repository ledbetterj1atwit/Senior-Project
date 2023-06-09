import pylatex
from sys import argv

if __name__ == "__main__":
    path = "doc_gen.pdf"
    try:
        path = argv[1]
    except IndexError:
        pass
    document = pylatex.Document()
    with document.create(pylatex.Section("Section One")):
        document.append(pylatex.MediumText("Hello, world."))
        document.append("Im going to **** someone\n")
        document.append("This took an HOUR!!!")
    with document.create(pylatex.Section("Section Two")):
        document.append("Im getting lunch...")

    document.generate_pdf(path, clean_tex=False)
