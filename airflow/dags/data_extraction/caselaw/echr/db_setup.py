from data_extraction.caselaw.echr.echr_extraction import echr_extract
from data_loading.data_loader import load_data
from data_transformation.data_transformer import transform_data


def get_echr_setup_args(last_index):
    """
    ECHR database setup routine - for building entire DB from scratch.
    This method returns the start&end dates for extraction
    Index referenced in code is the index of last visited point in the var_list.
    Proper usage will setup the entire database, with small increments, year by year.
    """
    var_list = ['1995-01-01', '1996-01-01', '1997-01-01', '1998-01-01', '1999-01-01', '2000-01-01', '2001-01-01',
                '2002-01-01',
                '2003-01-01', '2004-01-01', '2005-01-01', '2006-01-01', '2007-01-01', '2008-01-01', '2009-01-01',
                '2010-01-01',
                '2011-01-01', '2012-01-01', '2013-01-01', '2014-01-01', '2015-01-01', '2016-01-01', '2017-01-01',
                '2018-01-01',
                '2019-01-01', '2020-01-01', '2021-01-01', '2022-01-01', '2023-01-01']
    next_index = last_index + 1  # end index
    if last_index >= len(var_list):  # if start is out, no extraction out
        starting = None
        ending = None
    elif last_index >= 0:  # starting is in
        starting = var_list[last_index]
        if next_index >= len(var_list):  # determine if end is there or no
            ending = None
        else:
            ending = var_list[next_index]
    else:
        starting = None
        ending = var_list[0]

    return starting, ending


if __name__ == "__main__":
    for i in range(-1, 29):
        starting, ending = get_echr_setup_args(i)
        if starting and ending:
            echr_extract(["--start-date", starting, "--end-date", ending])
        elif starting:
            echr_extract(["--start-date", starting])
        elif ending:
            echr_extract(["--end-date", ending])
        transform_data()
        load_data()
