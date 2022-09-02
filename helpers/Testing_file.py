from helpers.csv_manipulator import *
from helpers.citations_adder import *
from helpers.fulltext_saving import *
from helpers.json_to_csv import *
from helpers.sparql import *
def get_eurovoc(text):
    try:
        start = text.find("EUROVOC")
        try:
            ending=text.find("Subject matter")
        except:
            try:
                ending=text.find("Directory code")
            except:
                try:
                    ending=text.find("Miscellaneous information")
                except:
                    ending=start
        if ending is start:
            return ""
        else:
            text=text[start:ending]
            texts = text.split("\n")
            lists = []
            for t in texts:
                if "EUROVOC" not in t and t != "":
                    lists.append(t)
            return "_".join(lists)
    except:
        return ""
if __name__ == '__main__':
    link = "https://eur-lex.europa.eu/legal-content/EN/ALL/?uri=CELEX:52018IP0428&qid=1662057930872"
    html=response_wrapper(link)
    text = get_full_text_from_html(html.text)
    print(get_eurovoc(text))
