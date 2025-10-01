def strip_lido_law_id(lido_law_id):
    if lido_law_id[0:43] == "http://linkeddata.overheid.nl/terms/bwb/id/" and len(lido_law_id) > 43:
        return lido_law_id[43:]
    return None
