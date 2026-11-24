-- Procedural timeline of one case (roadmap R5.3): every case reachable from
-- %(case_id)s through case_procedural_link (caselaw-coolify migration 0013),
-- in either direction, up to %(max_depth)s hops, and the links between them,
-- oldest first. One row per (earlier, later, step); the relation types,
-- datasets and highest confidence behind it are aggregated.
--
-- Parameters (psycopg2 named style): case_id bigint, max_depth int (6 is
-- plenty: referral -> ruling -> follow-up, or first instance -> appeal ->
-- cassation -> referral -> ruling). The walk keeps (case, depth) pairs with
-- UNION, so cycles and dense components stay bounded by depth x members.
WITH RECURSIVE walk (case_id, depth) AS (
    SELECT %(case_id)s::bigint, 0
  UNION
    SELECT n.other, w.depth + 1
      FROM walk w
      CROSS JOIN LATERAL (
          SELECT l.later_case_id AS other
            FROM cle_v2.case_procedural_link l
           WHERE l.earlier_case_id = w.case_id
          UNION
          SELECT l.earlier_case_id
            FROM cle_v2.case_procedural_link l
           WHERE l.later_case_id = w.case_id
      ) n
     WHERE w.depth < %(max_depth)s
),
members AS (
    SELECT case_id, min(depth) AS depth FROM walk GROUP BY case_id
)
SELECT l.earlier_case_id,
       e.ecli AS earlier_ecli,
       e.celex_id AS earlier_celex,
       e.date_decision AS earlier_date,
       l.later_case_id,
       la.ecli AS later_ecli,
       la.celex_id AS later_celex,
       la.date_decision AS later_date,
       l.step,
       array_agg(DISTINCT l.relation_type ORDER BY l.relation_type) AS relation_types,
       array_agg(DISTINCT l.source_dataset ORDER BY l.source_dataset) AS source_datasets,
       max(l.confidence) AS confidence,
       least(m1.depth, m2.depth) AS distance
  FROM cle_v2.case_procedural_link l
  JOIN members m1 ON m1.case_id = l.earlier_case_id
  JOIN members m2 ON m2.case_id = l.later_case_id
  JOIN cle_v2.cases e ON e.id = l.earlier_case_id
  JOIN cle_v2.cases la ON la.id = l.later_case_id
 GROUP BY l.earlier_case_id, e.ecli, e.celex_id, e.date_decision,
          l.later_case_id, la.ecli, la.celex_id, la.date_decision, l.step,
          m1.depth, m2.depth
 ORDER BY e.date_decision NULLS LAST, la.date_decision NULLS LAST, l.earlier_case_id,
          l.later_case_id, l.step
