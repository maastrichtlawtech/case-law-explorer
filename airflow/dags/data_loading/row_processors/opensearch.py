from definitions.storage_handler import CSV_RS_CASES, CSV_RS_OPINIONS, CSV_LI_CASES, CSV_CASE_CITATIONS, \
    CSV_LEGISLATION_CITATIONS, CSV_OS_ECLIS_FAILED, get_path_raw, get_path_processed
from definitions.terminology.attribute_names import RS_SUBJECT, RS_RELATION, RS_REFERENCES, RS_HASVERSION, ECLI_DECISION, \
    ECLI, ECLI_OPINION, LI_LAW_AREA, LIDO_JURISPRUDENTIE, LIDO_ARTIKEL_TITLE

SET_SEP = '; '              # used to separate set items in string
LI = '_li'


class OpenSearchRowProcessor:
    def __init__(self, path, es_client):
        self.path = path
        self.client = es_client
        self.row_processor = self._get_row_processor()

    def _get_row_processor(self):
        def row_processor_rs_cases(row):
            update_items = []
            update_set_items = []
            # transform set attributes  to lists
            # (domains, predecessor_successor_cases, references_legislation, alternative_sources)
            for attribute in [RS_RELATION, RS_REFERENCES, RS_SUBJECT, RS_HASVERSION]:
                if attribute in row:
                    row[attribute] = row[attribute].split(SET_SEP)
            put_items = [row]
            return put_items, update_items, update_set_items

        def row_processor_rs_opinions(row):
            put_items, update_items, update_set_items = row_processor_rs_cases(row)
            if ECLI_DECISION in row:
                update_items.append({
                    ECLI: row[ECLI_DECISION],
                    ECLI_OPINION: row[ECLI]
                })
            return put_items, update_items, update_set_items

        def row_processor_li_cases(row):
            put_items = []
            update_set_items = []
            if LI_LAW_AREA in row:
                row[LI_LAW_AREA] = row[LI_LAW_AREA].split(SET_SEP)
            row_li = {ECLI: row[ECLI]}
            for key in row.keys() - ECLI:
                row_li[key + LI] = row[key]
            update_items = [row_li]
            return put_items, update_items, update_set_items

        # @TODO: replace attribute names with global definition
        def row_processor_c_citations(row):
            put_items = []
            update_items = []
            update_set_items = []
            if row['keep1'] == 'True':
                update_set_items = [{
                    ECLI: row[ECLI],
                    'cites': row[LIDO_JURISPRUDENTIE]
                }, {
                    ECLI: row[LIDO_JURISPRUDENTIE],
                    'cited_by': row[ECLI]
                }]
            return put_items, update_items, update_set_items

        def row_processor_l_citations(row):
            put_items = []
            update_items = []
            update_set_items = [{
                ECLI: row[ECLI],
                'legal_provisions': row[LIDO_ARTIKEL_TITLE]
            }]
            return put_items, update_items, update_set_items

        processor_map = {
            get_path_processed(CSV_RS_CASES): row_processor_rs_cases,
            get_path_processed(CSV_RS_OPINIONS): row_processor_rs_opinions,
            get_path_processed(CSV_LI_CASES): row_processor_li_cases,
            get_path_raw(CSV_CASE_CITATIONS): row_processor_c_citations,
            get_path_raw(CSV_LEGISLATION_CITATIONS): row_processor_l_citations
        }
        return processor_map.get(self.path)

    def upload_row(self, row):
        item_counter = 0

        put_items, update_items, update_set_items = self.row_processor(row)

        for item in put_items:
            try:
                response = self.client.es.index(
                    index=self.client.index_name,
                    doc_type='_doc',
                    id=item[ECLI],
                    body=item,
                    filter_path='_shards.failed'
                )
                item_counter += 1
                if response['_shards']['failed'] != 0:
                    raise Exception('Shard indexing failed.')
            except Exception as e:
                print(e, item[ECLI])
                with open(get_path_processed(CSV_OS_ECLIS_FAILED), 'a') as f:
                    f.write(item[ECLI] + '\n')

        # add/overwrite attributes to document. If document does not yet exist, create new document.
        for item in update_items:
            item_id = item[ECLI]
            item.pop(ECLI)
            try:
                response = self.client.es.update(
                    index=self.client.index_name,
                    doc_type='_doc',
                    id=item_id,
                    body={
                        'doc': item,
                        'upsert': {
                            ECLI: item_id,
                            **item
                        }
                    },
                    filter_path='_shards.failed'
                )
                if response['_shards']['failed'] != 0:
                    raise Exception('Shard indexing failed.')
            except Exception as e:
                print(e, item_id)
                with open(get_path_processed(CSV_OS_ECLIS_FAILED), 'a') as f:
                    f.write(item_id + '\n')

        # add member to set attribute of document. If document does not yet exist, create new document.
        for item in update_set_items:
            item_id = item[ECLI]
            item.pop(ECLI)
            for attribute in item.keys():
                try:
                    response = self.client.es.update(
                        index=self.client.index_name,
                        doc_type='_doc',
                        id=item_id,
                        body={
                            'script': {
                                'source': f'if (ctx._source.{attribute} != null) '
                                          f'{{if (ctx._source.{attribute}.contains(params.{attribute})) '
                                          f'{{ctx.op = "none"}} else {{ctx._source.{attribute}.add(params.{attribute})}}}}'
                                          f'else {{ctx._source.{attribute} = [params.{attribute}]}}',
                                'params': {
                                    attribute: item[attribute]
                                }
                            },
                            'upsert': {
                                ECLI: item_id,
                                attribute: [item[attribute]]
                            }
                        },
                        filter_path='_shards.failed'
                    )
                    if response['_shards']['failed'] != 0:
                        raise Exception('Shard indexing failed.')
                except Exception as e:
                    print(e, item_id, item)
                    with open(get_path_processed(CSV_OS_ECLIS_FAILED), 'a') as f:
                        f.write(item_id + '\n')

        return item_counter
