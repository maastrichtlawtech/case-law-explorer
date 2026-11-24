CREATE SCHEMA "public";
CREATE SCHEMA "cle_v2";
CREATE SCHEMA "legacy";
CREATE EXTENSION IF NOT EXISTS "vector";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";
CREATE TABLE "cle_v2"."_lang_map" (
	"hudoc" text PRIMARY KEY,
	"iso" text NOT NULL
);
CREATE TABLE "cle_v2"."case_citation" (
	"id" bigint PRIMARY KEY GENERATED ALWAYS AS IDENTITY (sequence name "cle_v2"."case_citation_id_seq" INCREMENT BY 1 MINVALUE 1 MAXVALUE 9223372036854775807 START WITH 1 CACHE 1),
	"source_case_id" bigint,
	"target_case_id" bigint,
	"target_ecli_raw" text,
	"target_celex_raw" text,
	"relation_type" text,
	"source_dataset" text NOT NULL,
	"weight" integer DEFAULT 1,
	"context_segment_id" bigint,
	"is_cross_jurisdiction" boolean DEFAULT false,
	"extractor_at" timestamp with time zone DEFAULT now(),
	"extractor_version" text
);
CREATE TABLE "cle_v2"."case_citation_counts" (
	"case_id" bigint PRIMARY KEY,
	"cites_count" integer DEFAULT 0 NOT NULL,
	"cited_by_count" integer DEFAULT 0 NOT NULL,
	"updated_at" timestamp with time zone DEFAULT now() NOT NULL
);
CREATE TABLE "cle_v2"."case_cluster" (
	"id" bigint PRIMARY KEY GENERATED ALWAYS AS IDENTITY (sequence name "cle_v2"."case_cluster_id_seq" INCREMENT BY 1 MINVALUE 1 MAXVALUE 9223372036854775807 START WITH 1 CACHE 1),
	"snapshot_id" bigint,
	"algorithm" text,
	"label" text,
	"size" integer
);
CREATE TABLE "cle_v2"."case_cluster_membership" (
	"cluster_id" bigint,
	"case_id" bigint,
	CONSTRAINT "case_cluster_membership_pkey" PRIMARY KEY("cluster_id","case_id")
);
CREATE TABLE "cle_v2"."case_domain" (
	"case_id" bigint,
	"domain_id" bigint,
	CONSTRAINT "case_domain_pkey" PRIMARY KEY("case_id","domain_id")
);
CREATE TABLE "cle_v2"."case_entity" (
	"id" bigint PRIMARY KEY GENERATED ALWAYS AS IDENTITY (sequence name "cle_v2"."case_entity_id_seq" INCREMENT BY 1 MINVALUE 1 MAXVALUE 9223372036854775807 START WITH 1 CACHE 1),
	"case_id" bigint,
	"entity_type" text,
	"canonical_name" text,
	"surface_form" text,
	"uri" text,
	"char_start" integer,
	"char_end" integer,
	"confidence" real
);
CREATE TABLE "cle_v2"."case_judge" (
	"id" bigint PRIMARY KEY GENERATED ALWAYS AS IDENTITY (sequence name "cle_v2"."case_judge_id_seq" INCREMENT BY 1 MINVALUE 1 MAXVALUE 9223372036854775807 START WITH 1 CACHE 1),
	"case_id" bigint,
	"judge_id" bigint,
	"role" text,
	CONSTRAINT "case_judge_case_id_judge_id_role_key" UNIQUE("case_id","judge_id","role")
);
CREATE TABLE "cle_v2"."case_law_reference" (
	"id" bigint PRIMARY KEY GENERATED ALWAYS AS IDENTITY (sequence name "cle_v2"."case_law_reference_id_seq" INCREMENT BY 1 MINVALUE 1 MAXVALUE 9223372036854775807 START WITH 1 CACHE 1),
	"case_id" bigint NOT NULL,
	"legislation_id" bigint,
	"provision_id" bigint,
	"raw_scheme" text,
	"raw_resource" text,
	"raw_subdivision" text,
	"raw_label_id" bigint,
	"raw_reference" text,
	"version_date" date,
	"role" text DEFAULT 'cited' NOT NULL,
	"source_dataset" text NOT NULL,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL
);
CREATE TABLE "cle_v2"."case_network_metric" (
	"snapshot_id" bigint,
	"case_id" bigint,
	"in_degree" integer,
	"out_degree" integer,
	"pagerank" real,
	"betweenness" real,
	"hub_score" real,
	"authority_score" real,
	"eigenvector" real,
	CONSTRAINT "case_network_metric_pkey" PRIMARY KEY("snapshot_id","case_id")
);
CREATE TABLE "cle_v2"."case_party" (
	"case_id" bigint,
	"party_id" bigint,
	"role" text,
	"ordinal" smallint DEFAULT 1,
	CONSTRAINT "case_party_pkey" PRIMARY KEY("case_id","party_id","role","ordinal")
);
CREATE TABLE "cle_v2"."case_segment" (
	"id" bigint PRIMARY KEY GENERATED ALWAYS AS IDENTITY (sequence name "cle_v2"."case_segment_id_seq" INCREMENT BY 1 MINVALUE 1 MAXVALUE 9223372036854775807 START WITH 1 CACHE 1),
	"case_id" bigint,
	"language" text,
	"segment_type" text,
	"segment_index" integer,
	"segment_text" text,
	"segment_hash" text,
	"embedding" vector(768),
	"embedding_model" text,
	"extractor_version" text,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL,
	CONSTRAINT "case_segment_case_id_segment_hash_key" UNIQUE("case_id","segment_hash")
);
CREATE TABLE "cle_v2"."case_summary_version" (
	"id" bigint PRIMARY KEY GENERATED ALWAYS AS IDENTITY (sequence name "cle_v2"."case_summary_version_id_seq" INCREMENT BY 1 MINVALUE 1 MAXVALUE 9223372036854775807 START WITH 1 CACHE 1),
	"case_id" bigint NOT NULL,
	"language" text,
	"summary_text" text NOT NULL,
	"summary_embedding" vector(768),
	"embedding_model" text,
	"summarization_model" text,
	"segment_scope" text NOT NULL,
	"version_number" integer DEFAULT 1 NOT NULL,
	"is_current" boolean DEFAULT true NOT NULL,
	"generation_source" text NOT NULL,
	"rejected_at" timestamp with time zone,
	"rejection_reason" text,
	"parent_version_id" bigint,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL
);
CREATE TABLE "cle_v2"."case_text" (
	"id" bigint PRIMARY KEY GENERATED ALWAYS AS IDENTITY (sequence name "cle_v2"."case_text_id_seq" INCREMENT BY 1 MINVALUE 1 MAXVALUE 9223372036854775807 START WITH 1 CACHE 1),
	"case_id" bigint NOT NULL,
	"language" text NOT NULL,
	"fulltext" text,
	"summary" text,
	"summary_source" text,
	"fulltext_tsv" tsvector GENERATED ALWAYS AS (to_tsvector('simple'::regconfig, COALESCE(fulltext, ''::text))) STORED,
	"summary_tsv" tsvector GENERATED ALWAYS AS (to_tsvector('simple'::regconfig, COALESCE(summary, ''::text))) STORED,
	"summary_embedding" vector(768),
	"embedding_model" text,
	"source" text NOT NULL,
	"text_format" text,
	"missing_reasons" text,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL,
	"updated_at" timestamp with time zone DEFAULT now() NOT NULL,
	"is_stub" boolean DEFAULT false NOT NULL,
	CONSTRAINT "case_text_case_id_language_source_key" UNIQUE("case_id","language","source")
);
CREATE TABLE "cle_v2"."cases" (
	"id" bigint PRIMARY KEY GENERATED ALWAYS AS IDENTITY (sequence name "cle_v2"."cases_id_seq" INCREMENT BY 1 MINVALUE 1 MAXVALUE 9223372036854775807 START WITH 1 CACHE 1),
	"ecli" text CONSTRAINT "cases_ecli_key" UNIQUE,
	"item_id" text CONSTRAINT "cases_item_id_key" UNIQUE,
	"celex_id" text CONSTRAINT "cases_celex_id_key" UNIQUE,
	"title" text,
	"date_decision" date,
	"date_published" date,
	"court_id" bigint,
	"language_iso" text,
	"document_type_id" bigint,
	"procedure_type_id" bigint,
	"instance_id" bigint,
	"case_number" text,
	"importance" smallint,
	"is_landmark" boolean,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL,
	"updated_at" timestamp with time zone DEFAULT now() NOT NULL,
	"sources" text[] NOT NULL
);
CREATE TABLE "cle_v2"."cjeu_ag_opinion" (
	"id" bigint PRIMARY KEY GENERATED ALWAYS AS IDENTITY (sequence name "cle_v2"."cjeu_ag_opinion_id_seq" INCREMENT BY 1 MINVALUE 1 MAXVALUE 9223372036854775807 START WITH 1 CACHE 1),
	"case_id" bigint NOT NULL CONSTRAINT "cjeu_ag_opinion_case_id_key" UNIQUE,
	"parent_case_id" bigint,
	"advocate_general" text,
	"opinion_uri" text,
	"delivered_date" date
);
CREATE TABLE "cle_v2"."cjeu_document" (
	"id" bigint PRIMARY KEY GENERATED ALWAYS AS IDENTITY (sequence name "cle_v2"."cjeu_document_id_seq" INCREMENT BY 1 MINVALUE 1 MAXVALUE 9223372036854775807 START WITH 1 CACHE 1),
	"case_id" bigint NOT NULL CONSTRAINT "cjeu_document_case_id_key" UNIQUE,
	"celex_id" text,
	"ecli" text,
	"sector" text,
	"case_number" text,
	"formation_id" bigint,
	"proc_type" text,
	"procedure_result" text,
	"date_lodged" date,
	"cellar_uri" text,
	"work_uri" text,
	"journal_refs" text,
	"erecueil_ref" text,
	"local_identifier" text,
	"dossier_uri" text,
	"dossier_parent_case_id" bigint,
	"citations_extra_info" text,
	"national_judgement_xml" text
);
CREATE TABLE "cle_v2"."cjeu_national_document" (
	"id" bigint PRIMARY KEY GENERATED ALWAYS AS IDENTITY (sequence name "cle_v2"."cjeu_national_document_id_seq" INCREMENT BY 1 MINVALUE 1 MAXVALUE 9223372036854775807 START WITH 1 CACHE 1),
	"case_id" bigint NOT NULL CONSTRAINT "cjeu_national_document_case_id_key" UNIQUE,
	"national_court_uri" text,
	"national_decision_internal_id" text,
	"national_parties_raw" text,
	"national_keywords" text,
	"national_reference_publication" text,
	"national_reference_publication_conclusion" text,
	"national_follow_up" text,
	"national_judgement_reference" text,
	"national_act_reference_national" text,
	"national_act_reference_international" text,
	"national_act_reference_european" text,
	"national_based_on_resource_legal" text
);
CREATE TABLE "cle_v2"."court" (
	"id" bigint PRIMARY KEY GENERATED ALWAYS AS IDENTITY (sequence name "cle_v2"."court_id_seq" INCREMENT BY 1 MINVALUE 1 MAXVALUE 9223372036854775807 START WITH 1 CACHE 1),
	"code" text CONSTRAINT "court_code_key" UNIQUE,
	"name" text,
	"level" text,
	"jurisdiction_id" bigint,
	"parent_court_id" bigint
);
CREATE TABLE "cle_v2"."court_formation" (
	"id" bigint PRIMARY KEY GENERATED ALWAYS AS IDENTITY (sequence name "cle_v2"."court_formation_id_seq" INCREMENT BY 1 MINVALUE 1 MAXVALUE 9223372036854775807 START WITH 1 CACHE 1),
	"code" text CONSTRAINT "court_formation_code_key" UNIQUE,
	"label" text,
	"judge_count" smallint
);
CREATE TABLE "cle_v2"."document_type" (
	"id" bigint PRIMARY KEY GENERATED ALWAYS AS IDENTITY (sequence name "cle_v2"."document_type_id_seq" INCREMENT BY 1 MINVALUE 1 MAXVALUE 9223372036854775807 START WITH 1 CACHE 1),
	"code" text CONSTRAINT "document_type_code_key" UNIQUE,
	"name" text
);
CREATE TABLE "cle_v2"."domain" (
	"id" bigint PRIMARY KEY GENERATED ALWAYS AS IDENTITY (sequence name "cle_v2"."domain_id_seq" INCREMENT BY 1 MINVALUE 1 MAXVALUE 9223372036854775807 START WITH 1 CACHE 1),
	"scheme" text,
	"name" text,
	"uri" text,
	"parent_id" bigint
);
CREATE TABLE "cle_v2"."domain_label" (
	"domain_id" bigint,
	"language" text,
	"label" text NOT NULL,
	CONSTRAINT "domain_label_pkey" PRIMARY KEY("domain_id","language")
);
CREATE TABLE "cle_v2"."echr_document" (
	"item_id" text PRIMARY KEY,
	"case_id" bigint NOT NULL,
	"language" text NOT NULL,
	"extractedappno" text,
	"docname" text,
	"doctype" text,
	"doctype_branch" text,
	"judgement_date" timestamp with time zone,
	"reference_date" timestamp with time zone,
	"article" text,
	"conclusion" text,
	"violation" text,
	"nonviolation" text,
	"respondent" text,
	"originating_body" integer,
	"represented_by" text,
	"published_by" text,
	"rules_of_court" text,
	"applicability" text,
	"separate_opinion" text,
	"issue" text,
	"importance" smallint,
	"rank" numeric,
	"scl" text,
	"external_sources" text,
	"judgement_year" integer GENERATED ALWAYS AS ((EXTRACT(year FROM (judgement_date AT TIME ZONE 'UTC'::text)))::integer) STORED,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL,
	"updated_at" timestamp with time zone DEFAULT now() NOT NULL
);
CREATE TABLE "cle_v2"."echr_document_appno" (
	"item_id" text,
	"appno" text,
	"source" text,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL,
	CONSTRAINT "echr_document_appno_pkey" PRIMARY KEY("item_id","appno","source")
);
CREATE TABLE "cle_v2"."echr_document_article" (
	"item_id" text,
	"kind" text,
	"article_code" text,
	"protocol" text,
	"raw" text,
	CONSTRAINT "echr_document_article_pkey" PRIMARY KEY("item_id","kind","article_code"),
	CONSTRAINT "echr_document_article_kind_check" CHECK ((kind = ANY (ARRAY['applied'::text, 'violation'::text, 'nonviolation'::text])))
);
CREATE TABLE "cle_v2"."echr_document_secondary_text" (
	"item_id" text PRIMARY KEY,
	"fulltext" text NOT NULL,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL
);
CREATE TABLE "cle_v2"."echr_extractor_segments" (
	"item_id" text PRIMARY KEY,
	"parser_mode" text,
	"error" text,
	"procedure" text,
	"facts" text,
	"complaints" text,
	"law" text,
	"operative" text,
	"subject_matter" text,
	"court_assessment" text,
	"separate_opinion" text,
	"appendix" text,
	"num_sections" integer DEFAULT 0 NOT NULL,
	"segmented_at" timestamp with time zone DEFAULT now() NOT NULL,
	"extractor_version" text
);
CREATE TABLE "cle_v2"."instance" (
	"id" bigint PRIMARY KEY GENERATED ALWAYS AS IDENTITY (sequence name "cle_v2"."instance_id_seq" INCREMENT BY 1 MINVALUE 1 MAXVALUE 9223372036854775807 START WITH 1 CACHE 1),
	"code" text CONSTRAINT "instance_code_key" UNIQUE,
	"name" text
);
CREATE TABLE "cle_v2"."judge" (
	"id" bigint PRIMARY KEY GENERATED ALWAYS AS IDENTITY (sequence name "cle_v2"."judge_id_seq" INCREMENT BY 1 MINVALUE 1 MAXVALUE 9223372036854775807 START WITH 1 CACHE 1),
	"full_name" text,
	"aliases" text[],
	"court_id" bigint
);
CREATE TABLE "cle_v2"."jurisdiction" (
	"id" bigint PRIMARY KEY GENERATED ALWAYS AS IDENTITY (sequence name "cle_v2"."jurisdiction_id_seq" INCREMENT BY 1 MINVALUE 1 MAXVALUE 9223372036854775807 START WITH 1 CACHE 1),
	"iso_code" text CONSTRAINT "jurisdiction_iso_code_key" UNIQUE,
	"name" text,
	"type" text
);
CREATE TABLE "cle_v2"."language" (
	"iso_code" text PRIMARY KEY,
	"name" text
);
-- Seed for the FKs on case_text.language / cases.language_iso: the 24
-- official EU languages (ISO 639-1), covering CJEU/Cellar and ECHR/HUDOC
-- member-state languages as well as Rechtspraak's "nl".
INSERT INTO "cle_v2"."language" ("iso_code", "name") VALUES
	('bg', 'Bulgarian'),
	('hr', 'Croatian'),
	('cs', 'Czech'),
	('da', 'Danish'),
	('nl', 'Dutch'),
	('en', 'English'),
	('et', 'Estonian'),
	('fi', 'Finnish'),
	('fr', 'French'),
	('de', 'German'),
	('el', 'Greek'),
	('hu', 'Hungarian'),
	('ga', 'Irish'),
	('it', 'Italian'),
	('lv', 'Latvian'),
	('lt', 'Lithuanian'),
	('mt', 'Maltese'),
	('pl', 'Polish'),
	('pt', 'Portuguese'),
	('ro', 'Romanian'),
	('sk', 'Slovak'),
	('sl', 'Slovenian'),
	('es', 'Spanish'),
	('sv', 'Swedish')
ON CONFLICT ("iso_code") DO NOTHING;
CREATE TABLE "cle_v2"."legal_provision" (
	"id" bigint PRIMARY KEY GENERATED ALWAYS AS IDENTITY (sequence name "cle_v2"."legal_provision_id_seq" INCREMENT BY 1 MINVALUE 1 MAXVALUE 9223372036854775807 START WITH 1 CACHE 1),
	"legislation_id" bigint,
	"parent_id" bigint,
	"element_type" text,
	"article_label" text,
	"title" text,
	"paragraph" text,
	"text" text,
	"bwb_label_id" bigint,
	"lido_id" text CONSTRAINT "legal_provision_lido_id_key" UNIQUE,
	-- jc_id is NOT reliably unique in real LIDO data (distinct dated lido_id
	-- nodes for the same provision can share a jci1.3 reference); lido_id is
	-- the actual unique natural key here. Discovered when the first real
	-- lido_postgres-successor merge hit a UniqueViolation on this constraint.
	"jc_id" text,
	"effective_from" date,
	"effective_to" date,
	"snapshot_date" date
);
CREATE TABLE "cle_v2"."legislation" (
	"id" bigint PRIMARY KEY GENERATED ALWAYS AS IDENTITY (sequence name "cle_v2"."legislation_id_seq" INCREMENT BY 1 MINVALUE 1 MAXVALUE 9223372036854775807 START WITH 1 CACHE 1),
	"identifier" text,
	"scheme" text,
	"title" text,
	"jurisdiction_id" bigint,
	"document_type" text,
	"enacted_date" date,
	"lido_id" text CONSTRAINT "legislation_lido_id_key" UNIQUE,
	-- Same reasoning as legal_provision.jc_id: not reliably unique in real data.
	"jc_id" text,
	"snapshot_date" date
);
CREATE TABLE "cle_v2"."legislation_alias" (
	"id" bigint PRIMARY KEY GENERATED ALWAYS AS IDENTITY (sequence name "cle_v2"."legislation_alias_id_seq" INCREMENT BY 1 MINVALUE 1 MAXVALUE 9223372036854775807 START WITH 1 CACHE 1),
	"legislation_id" bigint,
	"alias" text,
	"source" text
);
CREATE TABLE "cle_v2"."lido_link" (
	"id" bigint PRIMARY KEY GENERATED ALWAYS AS IDENTITY (sequence name "cle_v2"."lido_link_id_seq" INCREMENT BY 1 MINVALUE 1 MAXVALUE 9223372036854775807 START WITH 1 CACHE 1),
	"source_case_id" bigint,
	"target_case_id" bigint,
	"source_ecli" text,
	"source_uri" text,
	"target_ecli" text,
	"target_uri" text,
	"target_provision_id" bigint,
	"link_type" text,
	"fetched_at" timestamp with time zone DEFAULT now()
);
CREATE TABLE "cle_v2"."migration_manifest" (
	"step" text PRIMARY KEY,
	"completed_at" timestamp with time zone DEFAULT now() NOT NULL,
	"rows_affected" bigint,
	"note" text
);
CREATE TABLE "cle_v2"."network_snapshot" (
	"id" bigint PRIMARY KEY GENERATED ALWAYS AS IDENTITY (sequence name "cle_v2"."network_snapshot_id_seq" INCREMENT BY 1 MINVALUE 1 MAXVALUE 9223372036854775807 START WITH 1 CACHE 1),
	"snapshot_date" date,
	"description" text,
	"node_count" integer,
	"edge_count" integer,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL
);
CREATE TABLE "cle_v2"."party" (
	"id" bigint PRIMARY KEY GENERATED ALWAYS AS IDENTITY (sequence name "cle_v2"."party_id_seq" INCREMENT BY 1 MINVALUE 1 MAXVALUE 9223372036854775807 START WITH 1 CACHE 1),
	"canonical_name" text,
	"aliases" text[],
	"role_class" text,
	"country_iso" text
);
CREATE TABLE "cle_v2"."procedure_type" (
	"id" bigint PRIMARY KEY GENERATED ALWAYS AS IDENTITY (sequence name "cle_v2"."procedure_type_id_seq" INCREMENT BY 1 MINVALUE 1 MAXVALUE 9223372036854775807 START WITH 1 CACHE 1),
	"code" text CONSTRAINT "procedure_type_code_key" UNIQUE,
	"name" text
);
CREATE TABLE "cle_v2"."rs_document" (
	"case_id" bigint PRIMARY KEY,
	"date_decision" date,
	"document_type" text,
	"instance" text,
	"domains" text[],
	"source" text DEFAULT 'Rechtspraak' NOT NULL,
	"jurisdiction_country" text DEFAULT 'NL' NOT NULL,
	"procedure_type" text,
	"url_publication" text,
	"legal_provisions" text[],
	"predecessor_successor_cases" text,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL,
	"updated_at" timestamp with time zone DEFAULT now() NOT NULL,
	"date_published" date,
	"date_issued" date,
	"date_modified" timestamp with time zone,
	"title" text,
	"language" text,
	"access_rights" text,
	"zittingsplaats" text,
	"replaces_identifier" text,
	"creator_uri" text,
	"vindplaatsen" text[],
	"subject_uris" text[],
	"zaaknummer" text,
	"opendata_status" text DEFAULT 'public' NOT NULL,
	CONSTRAINT "rs_document_opendata_status_check" CHECK ((opendata_status = ANY (ARRAY['public'::text, 'depublicated'::text])))
);
CREATE TABLE "cle_v2"."rs_document_external_authority" (
	"case_id" bigint,
	"kind" text DEFAULT 'other' NOT NULL,
	"name" text NOT NULL,
	"article" text,
	"raw" text,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL,
	CONSTRAINT "rs_document_external_authority_pkey" PRIMARY KEY("case_id","raw")
);
CREATE TABLE "cle_v2"."rs_document_formal_relation" (
	"case_id" bigint,
	"target_ecli" text,
	"target_identifier" text,
	"relation_type" text DEFAULT 'unknown',
	"aanleg" text DEFAULT 'unknown',
	"name" text,
	"disposition" text,
	"gevolg" text,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL,
	CONSTRAINT "rs_document_formal_relation_pkey" PRIMARY KEY("case_id","target_identifier","relation_type","aanleg")
);
CREATE TABLE "cle_v2"."rs_document_publication" (
	"case_id" bigint,
	"raw" text,
	"kind" text DEFAULT 'other' NOT NULL,
	"journal_abbr" text,
	"year" integer,
	"locator" text,
	"annotator" text,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL,
	CONSTRAINT "rs_document_publication_pkey" PRIMARY KEY("case_id","raw")
);
CREATE TABLE "cle_v2"."search_query_log" (
	"id" bigint PRIMARY KEY GENERATED ALWAYS AS IDENTITY (sequence name "cle_v2"."search_query_log_id_seq" INCREMENT BY 1 MINVALUE 1 MAXVALUE 9223372036854775807 START WITH 1 CACHE 1),
	"user_id" text,
	"raw_query" text,
	"parsed_intent" jsonb,
	"filters" jsonb,
	"strategy" text,
	"result_count" integer,
	"clicked_case_ids" text[],
	"created_at" timestamp with time zone DEFAULT now() NOT NULL
);
CREATE INDEX "case_citation_idx_relation_type" ON "cle_v2"."case_citation" ("relation_type");
CREATE INDEX "case_citation_idx_source" ON "cle_v2"."case_citation" ("source_case_id");
CREATE INDEX "case_citation_idx_source_target" ON "cle_v2"."case_citation" ("source_case_id","target_case_id");
CREATE INDEX "case_citation_idx_target" ON "cle_v2"."case_citation" ("target_case_id");
CREATE INDEX "case_citation_idx_target_celex_raw" ON "cle_v2"."case_citation" ("target_celex_raw");
CREATE INDEX "case_citation_idx_target_ecli_raw" ON "cle_v2"."case_citation" ("target_ecli_raw");
CREATE INDEX "case_citation_idx_weight" ON "cle_v2"."case_citation" ("weight");
CREATE UNIQUE INDEX "case_citation_uk_resolved" ON "cle_v2"."case_citation" ("source_case_id","target_case_id","relation_type","source_dataset") WHERE "target_case_id" IS NOT NULL;
CREATE UNIQUE INDEX "case_citation_uk_unresolved_celex" ON "cle_v2"."case_citation" ("source_case_id","target_celex_raw","relation_type","source_dataset") WHERE "target_case_id" IS NULL AND "target_celex_raw" IS NOT NULL;
CREATE UNIQUE INDEX "case_citation_uk_unresolved_ecli" ON "cle_v2"."case_citation" ("source_case_id","target_ecli_raw","relation_type","source_dataset") WHERE "target_case_id" IS NULL AND "target_ecli_raw" IS NOT NULL;
CREATE INDEX "case_domain_idx_domain_id" ON "cle_v2"."case_domain" ("domain_id");
CREATE INDEX "case_entity_idx_case_id" ON "cle_v2"."case_entity" ("case_id");
CREATE INDEX "case_judge_idx_case_id" ON "cle_v2"."case_judge" ("case_id");
CREATE INDEX "case_judge_idx_judge_id" ON "cle_v2"."case_judge" ("judge_id");
CREATE INDEX "case_law_reference_idx_case_id" ON "cle_v2"."case_law_reference" ("case_id");
CREATE INDEX "case_law_reference_idx_legislation" ON "cle_v2"."case_law_reference" ("legislation_id");
CREATE INDEX "case_law_reference_idx_provision" ON "cle_v2"."case_law_reference" ("provision_id");
CREATE INDEX "case_law_reference_idx_raw" ON "cle_v2"."case_law_reference" ("raw_scheme","raw_resource");
CREATE INDEX "case_law_reference_idx_raw_label" ON "cle_v2"."case_law_reference" ("raw_label_id");
CREATE UNIQUE INDEX "case_law_reference_uk_legislation" ON "cle_v2"."case_law_reference" ("case_id","legislation_id","role","source_dataset");
CREATE UNIQUE INDEX "case_law_reference_uk_provision" ON "cle_v2"."case_law_reference" ("case_id","provision_id","role","source_dataset");
CREATE UNIQUE INDEX "case_law_reference_uk_raw" ON "cle_v2"."case_law_reference" ("case_id","raw_scheme","raw_resource",COALESCE(raw_subdivision, ''::text),"role","source_dataset");
CREATE INDEX "case_network_metric_idx_case" ON "cle_v2"."case_network_metric" ("case_id");
CREATE INDEX "case_party_idx_party" ON "cle_v2"."case_party" ("party_id");
CREATE INDEX "case_segment_idx_case_id" ON "cle_v2"."case_segment" ("case_id");
CREATE INDEX "case_summary_version_idx_case" ON "cle_v2"."case_summary_version" ("case_id");
CREATE UNIQUE INDEX "case_summary_version_uk_current" ON "cle_v2"."case_summary_version" ("case_id","segment_scope","summarization_model");
CREATE INDEX "case_text_idx_case_id" ON "cle_v2"."case_text" ("case_id");
CREATE INDEX "case_text_idx_fulltext_tsv" ON "cle_v2"."case_text" USING gin ("fulltext_tsv");
CREATE INDEX "case_text_idx_stub" ON "cle_v2"."case_text" ("case_id");
CREATE INDEX "case_text_idx_summary_embedding" ON "cle_v2"."case_text" USING hnsw ("summary_embedding" vector_cosine_ops);
CREATE INDEX "case_text_idx_summary_tsv" ON "cle_v2"."case_text" USING gin ("summary_tsv");
CREATE INDEX "case_idx_case_number" ON "cle_v2"."cases" ("case_number");
CREATE INDEX "case_idx_case_number_trgm" ON "cle_v2"."cases" USING gin ("case_number" gin_trgm_ops);
CREATE INDEX "case_idx_court" ON "cle_v2"."cases" ("court_id");
CREATE INDEX "case_idx_date_decision" ON "cle_v2"."cases" ("date_decision");
CREATE INDEX "case_idx_date_ecli" ON "cle_v2"."cases" ("date_decision","ecli");
CREATE INDEX "case_idx_ecli" ON "cle_v2"."cases" ("ecli");
CREATE INDEX "case_idx_importance" ON "cle_v2"."cases" ("importance");
CREATE INDEX "case_idx_item_id" ON "cle_v2"."cases" ("item_id");
CREATE INDEX "case_idx_sources" ON "cle_v2"."cases" USING gin ("sources");
CREATE INDEX "case_idx_title_trgm" ON "cle_v2"."cases" USING gin ("title" gin_trgm_ops);
CREATE INDEX "cases_idx_case_number_btree" ON "cle_v2"."cases" ("case_number");
CREATE INDEX "echr_document_idx_case_lang" ON "cle_v2"."echr_document" ("case_id","language");
CREATE INDEX "echr_document_idx_docname_trgm" ON "cle_v2"."echr_document" USING gin ("docname" gin_trgm_ops);
CREATE INDEX "echr_document_idx_doctype" ON "cle_v2"."echr_document" ("doctype");
CREATE INDEX "echr_document_idx_doctype_branch" ON "cle_v2"."echr_document" ("doctype_branch");
CREATE INDEX "echr_document_idx_issue_trgm" ON "cle_v2"."echr_document" USING gin ("issue" gin_trgm_ops);
CREATE INDEX "echr_document_idx_judgement_date" ON "cle_v2"."echr_document" ("judgement_date");
CREATE INDEX "echr_document_idx_judgement_year" ON "cle_v2"."echr_document" ("judgement_year");
CREATE INDEX "echr_document_idx_originating_body" ON "cle_v2"."echr_document" ("originating_body");
CREATE INDEX "echr_document_idx_reference_date" ON "cle_v2"."echr_document" ("reference_date");
CREATE INDEX "echr_document_appno_idx_appno" ON "cle_v2"."echr_document_appno" ("appno");
CREATE INDEX "echr_document_appno_idx_source" ON "cle_v2"."echr_document_appno" ("source");
CREATE INDEX "echr_document_article_idx_filter" ON "cle_v2"."echr_document_article" ("kind","article_code");
CREATE INDEX "echr_extractor_segments_idx_num_sections" ON "cle_v2"."echr_extractor_segments" ("num_sections");
CREATE INDEX "echr_extractor_segments_idx_parser" ON "cle_v2"."echr_extractor_segments" ("parser_mode");
CREATE INDEX "legal_provision_idx_bwb_label" ON "cle_v2"."legal_provision" ("bwb_label_id");
CREATE INDEX "legal_provision_idx_lookup" ON "cle_v2"."legal_provision" ("legislation_id",lower(article_label),"element_type");
CREATE INDEX "legislation_idx_scheme_identifier" ON "cle_v2"."legislation" ("scheme","identifier");
CREATE INDEX "legislation_alias_idx_alias_lower" ON "cle_v2"."legislation_alias" (lower(alias));
CREATE INDEX "legislation_alias_idx_alias_trgm" ON "cle_v2"."legislation_alias" USING gin ("alias" gin_trgm_ops);
-- No unique constraint existed on this table before (safe to add now: table has
-- zero rows/writers). Needed by the lido_postgres -> cle_v2 merge (airflow/dags/lido/)
-- to upsert idempotently on reruns.
CREATE UNIQUE INDEX "legislation_alias_uk" ON "cle_v2"."legislation_alias" ("legislation_id", "alias");
CREATE INDEX "lido_link_idx_source_case" ON "cle_v2"."lido_link" ("source_case_id");
CREATE INDEX "lido_link_idx_target_case" ON "cle_v2"."lido_link" ("target_case_id");
CREATE INDEX "rs_document_idx_date_decision" ON "cle_v2"."rs_document" ("date_decision");
CREATE INDEX "rs_document_idx_date_issued" ON "cle_v2"."rs_document" ("date_issued");
CREATE INDEX "rs_document_idx_date_modified" ON "cle_v2"."rs_document" ("date_modified");
CREATE INDEX "rs_document_idx_domains_gin" ON "cle_v2"."rs_document" USING gin ("domains");
CREATE INDEX "rs_document_publication_idx_journal" ON "cle_v2"."rs_document_publication" ("journal_abbr");
ALTER TABLE "cle_v2"."case_citation" ADD CONSTRAINT "fk_case_citation_context" FOREIGN KEY ("context_segment_id") REFERENCES "cle_v2"."case_segment"("id") ON DELETE SET NULL;
ALTER TABLE "cle_v2"."case_citation" ADD CONSTRAINT "fk_case_citation_source" FOREIGN KEY ("source_case_id") REFERENCES "cle_v2"."cases"("id") ON DELETE CASCADE;
ALTER TABLE "cle_v2"."case_citation" ADD CONSTRAINT "fk_case_citation_target" FOREIGN KEY ("target_case_id") REFERENCES "cle_v2"."cases"("id") ON DELETE SET NULL;
ALTER TABLE "cle_v2"."case_citation_counts" ADD CONSTRAINT "fk_case_citation_counts" FOREIGN KEY ("case_id") REFERENCES "cle_v2"."cases"("id") ON DELETE CASCADE;
ALTER TABLE "cle_v2"."case_cluster" ADD CONSTRAINT "fk_case_cluster_snapshot" FOREIGN KEY ("snapshot_id") REFERENCES "cle_v2"."network_snapshot"("id") ON DELETE CASCADE;
ALTER TABLE "cle_v2"."case_cluster_membership" ADD CONSTRAINT "fk_case_cluster_membership_case" FOREIGN KEY ("case_id") REFERENCES "cle_v2"."cases"("id") ON DELETE CASCADE;
ALTER TABLE "cle_v2"."case_cluster_membership" ADD CONSTRAINT "fk_case_cluster_membership_clus" FOREIGN KEY ("cluster_id") REFERENCES "cle_v2"."case_cluster"("id") ON DELETE CASCADE;
ALTER TABLE "cle_v2"."case_domain" ADD CONSTRAINT "fk_case_domain_case" FOREIGN KEY ("case_id") REFERENCES "cle_v2"."cases"("id") ON DELETE CASCADE;
ALTER TABLE "cle_v2"."case_domain" ADD CONSTRAINT "fk_case_domain_domain" FOREIGN KEY ("domain_id") REFERENCES "cle_v2"."domain"("id");
ALTER TABLE "cle_v2"."case_entity" ADD CONSTRAINT "fk_case_entity_case" FOREIGN KEY ("case_id") REFERENCES "cle_v2"."cases"("id") ON DELETE CASCADE;
ALTER TABLE "cle_v2"."case_judge" ADD CONSTRAINT "fk_case_judge_case" FOREIGN KEY ("case_id") REFERENCES "cle_v2"."cases"("id") ON DELETE CASCADE;
ALTER TABLE "cle_v2"."case_judge" ADD CONSTRAINT "fk_case_judge_judge" FOREIGN KEY ("judge_id") REFERENCES "cle_v2"."judge"("id");
ALTER TABLE "cle_v2"."case_law_reference" ADD CONSTRAINT "fk_case_law_reference_case" FOREIGN KEY ("case_id") REFERENCES "cle_v2"."cases"("id") ON DELETE CASCADE;
ALTER TABLE "cle_v2"."case_law_reference" ADD CONSTRAINT "fk_case_law_reference_leg" FOREIGN KEY ("legislation_id") REFERENCES "cle_v2"."legislation"("id");
ALTER TABLE "cle_v2"."case_law_reference" ADD CONSTRAINT "fk_case_law_reference_prov" FOREIGN KEY ("provision_id") REFERENCES "cle_v2"."legal_provision"("id");
ALTER TABLE "cle_v2"."case_network_metric" ADD CONSTRAINT "fk_case_network_metric_case" FOREIGN KEY ("case_id") REFERENCES "cle_v2"."cases"("id") ON DELETE CASCADE;
ALTER TABLE "cle_v2"."case_network_metric" ADD CONSTRAINT "fk_case_network_metric_snapshot" FOREIGN KEY ("snapshot_id") REFERENCES "cle_v2"."network_snapshot"("id") ON DELETE CASCADE;
ALTER TABLE "cle_v2"."case_party" ADD CONSTRAINT "fk_case_party_case" FOREIGN KEY ("case_id") REFERENCES "cle_v2"."cases"("id") ON DELETE CASCADE;
ALTER TABLE "cle_v2"."case_party" ADD CONSTRAINT "fk_case_party_party" FOREIGN KEY ("party_id") REFERENCES "cle_v2"."party"("id");
ALTER TABLE "cle_v2"."case_segment" ADD CONSTRAINT "fk_case_segment_case" FOREIGN KEY ("case_id") REFERENCES "cle_v2"."cases"("id") ON DELETE CASCADE;
ALTER TABLE "cle_v2"."case_segment" ADD CONSTRAINT "fk_case_segment_language" FOREIGN KEY ("language") REFERENCES "cle_v2"."language"("iso_code");
ALTER TABLE "cle_v2"."case_summary_version" ADD CONSTRAINT "fk_case_summary_version_case" FOREIGN KEY ("case_id") REFERENCES "cle_v2"."cases"("id") ON DELETE CASCADE;
ALTER TABLE "cle_v2"."case_summary_version" ADD CONSTRAINT "fk_case_summary_version_language" FOREIGN KEY ("language") REFERENCES "cle_v2"."language"("iso_code");
ALTER TABLE "cle_v2"."case_summary_version" ADD CONSTRAINT "fk_case_summary_version_parent" FOREIGN KEY ("parent_version_id") REFERENCES "cle_v2"."case_summary_version"("id") ON DELETE SET NULL;
ALTER TABLE "cle_v2"."case_text" ADD CONSTRAINT "fk_case_text_case" FOREIGN KEY ("case_id") REFERENCES "cle_v2"."cases"("id") ON DELETE CASCADE;
ALTER TABLE "cle_v2"."case_text" ADD CONSTRAINT "fk_case_text_language" FOREIGN KEY ("language") REFERENCES "cle_v2"."language"("iso_code");
ALTER TABLE "cle_v2"."cases" ADD CONSTRAINT "fk_case_court" FOREIGN KEY ("court_id") REFERENCES "cle_v2"."court"("id");
ALTER TABLE "cle_v2"."cases" ADD CONSTRAINT "fk_case_document_type" FOREIGN KEY ("document_type_id") REFERENCES "cle_v2"."document_type"("id");
ALTER TABLE "cle_v2"."cases" ADD CONSTRAINT "fk_case_instance" FOREIGN KEY ("instance_id") REFERENCES "cle_v2"."instance"("id");
ALTER TABLE "cle_v2"."cases" ADD CONSTRAINT "fk_case_language" FOREIGN KEY ("language_iso") REFERENCES "cle_v2"."language"("iso_code");
ALTER TABLE "cle_v2"."cases" ADD CONSTRAINT "fk_case_procedure_type" FOREIGN KEY ("procedure_type_id") REFERENCES "cle_v2"."procedure_type"("id");
ALTER TABLE "cle_v2"."cjeu_ag_opinion" ADD CONSTRAINT "fk_cjeu_ag_opinion_case" FOREIGN KEY ("case_id") REFERENCES "cle_v2"."cases"("id") ON DELETE CASCADE;
ALTER TABLE "cle_v2"."cjeu_ag_opinion" ADD CONSTRAINT "fk_cjeu_ag_opinion_parent" FOREIGN KEY ("parent_case_id") REFERENCES "cle_v2"."cases"("id") ON DELETE SET NULL;
ALTER TABLE "cle_v2"."cjeu_document" ADD CONSTRAINT "fk_cjeu_document_case" FOREIGN KEY ("case_id") REFERENCES "cle_v2"."cases"("id") ON DELETE CASCADE;
ALTER TABLE "cle_v2"."cjeu_document" ADD CONSTRAINT "fk_cjeu_document_dossier" FOREIGN KEY ("dossier_parent_case_id") REFERENCES "cle_v2"."cases"("id") ON DELETE SET NULL;
ALTER TABLE "cle_v2"."cjeu_document" ADD CONSTRAINT "fk_cjeu_document_formation" FOREIGN KEY ("formation_id") REFERENCES "cle_v2"."court_formation"("id");
ALTER TABLE "cle_v2"."cjeu_national_document" ADD CONSTRAINT "fk_cjeu_national_document_case" FOREIGN KEY ("case_id") REFERENCES "cle_v2"."cases"("id") ON DELETE CASCADE;
ALTER TABLE "cle_v2"."court" ADD CONSTRAINT "fk_court_jurisdiction" FOREIGN KEY ("jurisdiction_id") REFERENCES "cle_v2"."jurisdiction"("id");
ALTER TABLE "cle_v2"."court" ADD CONSTRAINT "fk_court_parent_court" FOREIGN KEY ("parent_court_id") REFERENCES "cle_v2"."court"("id");
ALTER TABLE "cle_v2"."domain" ADD CONSTRAINT "fk_domain_parent" FOREIGN KEY ("parent_id") REFERENCES "cle_v2"."domain"("id");
ALTER TABLE "cle_v2"."domain_label" ADD CONSTRAINT "fk_domain_label_domain" FOREIGN KEY ("domain_id") REFERENCES "cle_v2"."domain"("id") ON DELETE CASCADE;
ALTER TABLE "cle_v2"."domain_label" ADD CONSTRAINT "fk_domain_label_language" FOREIGN KEY ("language") REFERENCES "cle_v2"."language"("iso_code");
ALTER TABLE "cle_v2"."echr_document" ADD CONSTRAINT "fk_echr_document_case" FOREIGN KEY ("case_id") REFERENCES "cle_v2"."cases"("id") ON DELETE CASCADE;
ALTER TABLE "cle_v2"."echr_document" ADD CONSTRAINT "fk_echr_document_language" FOREIGN KEY ("language") REFERENCES "cle_v2"."language"("iso_code");
ALTER TABLE "cle_v2"."echr_document_appno" ADD CONSTRAINT "fk_echr_document_appno_doc" FOREIGN KEY ("item_id") REFERENCES "cle_v2"."echr_document"("item_id") ON DELETE CASCADE;
ALTER TABLE "cle_v2"."echr_document_article" ADD CONSTRAINT "fk_echr_document_article_doc" FOREIGN KEY ("item_id") REFERENCES "cle_v2"."echr_document"("item_id") ON DELETE CASCADE;
ALTER TABLE "cle_v2"."echr_document_secondary_text" ADD CONSTRAINT "fk_echr_document_secondary_text_doc" FOREIGN KEY ("item_id") REFERENCES "cle_v2"."echr_document"("item_id") ON DELETE CASCADE;
ALTER TABLE "cle_v2"."echr_extractor_segments" ADD CONSTRAINT "fk_echr_extractor_segments_doc" FOREIGN KEY ("item_id") REFERENCES "cle_v2"."echr_document"("item_id") ON DELETE CASCADE;
ALTER TABLE "cle_v2"."judge" ADD CONSTRAINT "fk_judge_court" FOREIGN KEY ("court_id") REFERENCES "cle_v2"."court"("id");
ALTER TABLE "cle_v2"."legal_provision" ADD CONSTRAINT "fk_legal_provision" FOREIGN KEY ("legislation_id") REFERENCES "cle_v2"."legislation"("id");
ALTER TABLE "cle_v2"."legal_provision" ADD CONSTRAINT "fk_legal_provision_parent" FOREIGN KEY ("parent_id") REFERENCES "cle_v2"."legal_provision"("id");
ALTER TABLE "cle_v2"."legislation" ADD CONSTRAINT "fk_legislation_jurisdiction" FOREIGN KEY ("jurisdiction_id") REFERENCES "cle_v2"."jurisdiction"("id");
ALTER TABLE "cle_v2"."legislation_alias" ADD CONSTRAINT "fk_legislation_alias" FOREIGN KEY ("legislation_id") REFERENCES "cle_v2"."legislation"("id");
ALTER TABLE "cle_v2"."lido_link" ADD CONSTRAINT "fk_lido_link_source_case" FOREIGN KEY ("source_case_id") REFERENCES "cle_v2"."cases"("id") ON DELETE SET NULL;
ALTER TABLE "cle_v2"."lido_link" ADD CONSTRAINT "fk_lido_link_target_case" FOREIGN KEY ("target_case_id") REFERENCES "cle_v2"."cases"("id") ON DELETE SET NULL;
ALTER TABLE "cle_v2"."lido_link" ADD CONSTRAINT "fk_lido_link_target_provision" FOREIGN KEY ("target_provision_id") REFERENCES "cle_v2"."legal_provision"("id");
ALTER TABLE "cle_v2"."party" ADD CONSTRAINT "fk_party_country" FOREIGN KEY ("country_iso") REFERENCES "cle_v2"."jurisdiction"("iso_code");
ALTER TABLE "cle_v2"."rs_document" ADD CONSTRAINT "fk_rs_document_case" FOREIGN KEY ("case_id") REFERENCES "cle_v2"."cases"("id") ON DELETE CASCADE;
ALTER TABLE "cle_v2"."rs_document_external_authority" ADD CONSTRAINT "fk_rs_document_ext_authority" FOREIGN KEY ("case_id") REFERENCES "cle_v2"."rs_document"("case_id") ON DELETE CASCADE;
ALTER TABLE "cle_v2"."rs_document_formal_relation" ADD CONSTRAINT "fk_rs_document_formal_source" FOREIGN KEY ("case_id") REFERENCES "cle_v2"."rs_document"("case_id") ON DELETE CASCADE;
ALTER TABLE "cle_v2"."rs_document_formal_relation" ADD CONSTRAINT "fk_rs_document_formal_target" FOREIGN KEY ("target_ecli") REFERENCES "cle_v2"."cases"("ecli") ON DELETE SET NULL;
ALTER TABLE "cle_v2"."rs_document_publication" ADD CONSTRAINT "fk_rs_document_publication_case" FOREIGN KEY ("case_id") REFERENCES "cle_v2"."rs_document"("case_id") ON DELETE CASCADE;
-- Reconstructed: not captured anywhere before this fix (not in schema.sql, not
-- in git history, not in application code) despite being called by
-- rs_v_document_law_reference below. wetten.overheid.nl/linkeddata.overheid.nl
-- URLs need a locale-independent YYYY-MM-DD segment, which is what this
-- provides; to_char (not date::text) makes that independent of DateStyle.
CREATE OR REPLACE FUNCTION "cle_v2"."rs_date_to_iso"("d" date)
RETURNS text
LANGUAGE sql
IMMUTABLE
AS $$
    SELECT to_char(d, 'YYYY-MM-DD');
$$;
CREATE VIEW "cle_v2"."case_text_canonical" AS (SELECT DISTINCT ON (case_id, language) id, case_id, language, fulltext, summary, summary_source, fulltext_tsv, summary_tsv, summary_embedding, embedding_model, source, text_format, missing_reasons, created_at, updated_at FROM cle_v2.case_text t ORDER BY case_id, language, ( CASE source WHEN 'RECHTSPRAAK'::text THEN 1 WHEN 'HUDOC'::text THEN 2 WHEN 'INFOCURIA_BLOB_HTML'::text THEN 3 WHEN 'CELLAR_ITEM'::text THEN 4 ELSE 5 END), id);
CREATE VIEW "cle_v2"."echr_v_document_with_text" AS (SELECT d.item_id, d.case_id, d.language, d.extractedappno, d.docname, d.doctype, d.doctype_branch, d.judgement_date, d.reference_date, d.article, d.conclusion, d.violation, d.nonviolation, d.respondent, d.originating_body, d.represented_by, d.published_by, d.rules_of_court, d.applicability, d.separate_opinion, d.issue, d.importance, d.rank, d.scl, d.external_sources, d.judgement_year, d.created_at, d.updated_at, t.fulltext, t.fulltext_tsv FROM cle_v2.echr_document d LEFT JOIN cle_v2.case_text_canonical t ON t.case_id = d.case_id AND t.language = d.language);
CREATE VIEW "cle_v2"."echr_v_judgments_decisions" AS (SELECT item_id, case_id, language, extractedappno, docname, doctype, doctype_branch, judgement_date, reference_date, article, conclusion, violation, nonviolation, respondent, originating_body, represented_by, published_by, rules_of_court, applicability, separate_opinion, issue, importance, rank, scl, external_sources, judgement_year, created_at, updated_at FROM cle_v2.echr_document WHERE doctype ~~* '%JUD%'::text OR doctype ~~* '%DEC%'::text);
CREATE VIEW "cle_v2"."rs_v_document_law_reference" AS (SELECT r.case_id, c.ecli, r.raw_resource AS bwb_resource, COALESCE(r.raw_subdivision, ''::text) AS article, r.version_date, r.raw_label_id AS bwb_label_id, r.source_dataset AS source, r.raw_reference AS opschrift, ((('http://wetten.overheid.nl/id/'::text || r.raw_resource) || '/'::text) || COALESCE(cle_v2.rs_date_to_iso(r.version_date), '1900-01-01'::text)) || '/0'::text AS legal_provision_url, CASE WHEN r.raw_label_id IS NULL THEN NULL::text ELSE (((((('http://linkeddata.overheid.nl/terms/bwb/id/'::text || r.raw_resource) || '/'::text) || r.raw_label_id::text) || '/'::text) || COALESCE(cle_v2.rs_date_to_iso(r.version_date), '1900-01-01'::text)) || '/'::text) || COALESCE(cle_v2.rs_date_to_iso(r.version_date), '1900-01-01'::text) END AS legal_provision_url_lido FROM cle_v2.case_law_reference r JOIN cle_v2.cases c ON c.id = r.case_id WHERE r.raw_scheme = 'bwb'::text);
CREATE VIEW "cle_v2"."rs_v_document_legal_provisions" AS (SELECT DISTINCT c.ecli, lr.raw_reference AS legal_provision FROM cle_v2.case_law_reference lr JOIN cle_v2.cases c ON c.id = lr.case_id WHERE lr.raw_scheme = 'bwb'::text AND NULLIF(lr.raw_reference, ''::text) IS NOT NULL UNION SELECT DISTINCT c.ecli, lp.title AS legal_provision FROM cle_v2.case_law_reference lr JOIN cle_v2.cases c ON c.id = lr.case_id JOIN cle_v2.legal_provision lp ON lp.bwb_label_id = lr.raw_label_id WHERE lr.raw_scheme = 'bwb'::text AND lr.raw_label_id IS NOT NULL AND NULLIF(lp.title, ''::text) IS NOT NULL UNION SELECT DISTINCT c.ecli, lp.title AS legal_provision FROM cle_v2.case_law_reference lr JOIN cle_v2.cases c ON c.id = lr.case_id JOIN cle_v2.legislation lg ON lg.scheme = 'bwb'::text AND lg.identifier = lr.raw_resource JOIN cle_v2.legal_provision lp ON lp.legislation_id = lg.id AND lower(lp.article_label) = lower(lr.raw_subdivision) AND lp.element_type = 'artikel'::text WHERE lr.raw_scheme = 'bwb'::text AND NULLIF(lp.title, ''::text) IS NOT NULL UNION SELECT DISTINCT c.ecli, lg.title AS legal_provision FROM cle_v2.case_law_reference lr JOIN cle_v2.cases c ON c.id = lr.case_id JOIN cle_v2.legislation lg ON lg.scheme = 'bwb'::text AND lg.identifier = lr.raw_resource WHERE lr.raw_scheme = 'bwb'::text AND NULLIF(lg.title, ''::text) IS NOT NULL UNION SELECT DISTINCT c.ecli, (lg.title || ', Artikel '::text) || lr.raw_subdivision AS legal_provision FROM cle_v2.case_law_reference lr JOIN cle_v2.cases c ON c.id = lr.case_id JOIN cle_v2.legislation lg ON lg.scheme = 'bwb'::text AND lg.identifier = lr.raw_resource WHERE lr.raw_scheme = 'bwb'::text AND NULLIF(lg.title, ''::text) IS NOT NULL AND NULLIF(lr.raw_subdivision, ''::text) IS NOT NULL UNION SELECT DISTINCT c.ecli, (lg.title || ', Bijlage '::text) || lr.raw_subdivision AS legal_provision FROM cle_v2.case_law_reference lr JOIN cle_v2.cases c ON c.id = lr.case_id JOIN cle_v2.legislation lg ON lg.scheme = 'bwb'::text AND lg.identifier = lr.raw_resource WHERE lr.raw_scheme = 'bwb'::text AND NULLIF(lg.title, ''::text) IS NOT NULL AND NULLIF(lr.raw_subdivision, ''::text) IS NOT NULL AND lr.raw_reference ~~* '%bijlage%'::text);
CREATE VIEW "cle_v2"."rs_v_document_with_text" AS (SELECT d.case_id, d.date_decision, d.document_type, d.instance, d.domains, d.source, d.jurisdiction_country, d.procedure_type, d.url_publication, d.legal_provisions, d.predecessor_successor_cases, d.created_at, d.updated_at, d.date_published, d.date_issued, d.date_modified, d.title, d.language, d.access_rights, d.zittingsplaats, d.replaces_identifier, d.creator_uri, d.vindplaatsen, d.subject_uris, d.zaaknummer, d.opendata_status, t.summary, t.fulltext, t.fulltext_tsv FROM cle_v2.rs_document d LEFT JOIN cle_v2.case_text_canonical t ON t.case_id = d.case_id AND t.language = 'nl'::text);

-- =============================================================================
-- Mirrored from MaastrichtU-BISS/caselaw-coolify db/migrations (the deployed
-- schema): 0008_case_text_document_kind, 0009_cross_dataset_links and
-- 0010_case_citation_link_indexes. Keep in step with those files.
-- =============================================================================

-- ---- 0008_case_text_document_kind.sql ----
-- What document a case_text row holds, not just where it was fetched from.
--
-- `source` records the fetch route (CELLAR_ITEM, INFOCURIA_BLOB_HTML, ...),
-- which says nothing about what the text is. CJEU rows have mixed the
-- decision itself with abstracts of it (CELLAR `_SUM` summaries, `_INF`
-- information sheets, Official Journal notices) and with texts of other
-- documents filed under the wrong case (an Advocate General's opinion in a
-- judgment's slot). All of them looked like "the fulltext" of the case.
--
-- document_kind:
--   judgment | order | opinion | ruling | decision | other
--                  the decision itself (same vocabulary as document_type.code)
--   extract        a partial text of the decision (CELLAR `_EXT`)
--   summary        a summary of the decision (CELLAR `_SUM`, `_RES`)
--   information    an information sheet (CELLAR `_INF`)
--   oj_notice      the decision's Official Journal notice
--   misfiled       another document's text filed under this case; kept for
--                  provenance, never served as this case's text
--   NULL           not classified (Rechtspraak, HUDOC, rows loaded before
--                  classification); treated like the decision itself
-- document_celex: CELEX of the work the text was taken from, when known.

ALTER TABLE "cle_v2"."case_text"
    ADD COLUMN IF NOT EXISTS "document_kind" text,
    ADD COLUMN IF NOT EXISTS "document_celex" text;

ALTER TABLE "cle_v2"."case_text"
    DROP CONSTRAINT IF EXISTS "case_text_document_kind_check";
ALTER TABLE "cle_v2"."case_text"
    ADD CONSTRAINT "case_text_document_kind_check" CHECK (
        "document_kind" IN (
            'judgment', 'order', 'opinion', 'ruling', 'decision', 'other',
            'extract', 'summary', 'information', 'oj_notice', 'misfiled'
        )
    ) NOT VALID;

COMMENT ON COLUMN "cle_v2"."case_text"."document_kind" IS
    'What the text is: the decision itself (judgment, order, opinion, ruling, decision, other), an extract, summary, information sheet or OJ notice of it, or misfiled (another document''s text). NULL = not classified.';
COMMENT ON COLUMN "cle_v2"."case_text"."document_celex" IS
    'CELEX of the work the text was taken from, when known.';

-- One text per (case, language): the decision itself before extracts before
-- abstracts; within a kind, a non-empty text first, then the origin source
-- (Rechtspraak, HUDOC), then CELLAR, which is keyed by the document's own
-- CELEX, before InfoCuria. Misfiled texts are never served.
CREATE OR REPLACE VIEW "cle_v2"."case_text_canonical" AS
SELECT DISTINCT ON (t."case_id", t."language") t.*
FROM "cle_v2"."case_text" t
WHERE t."document_kind" IS DISTINCT FROM 'misfiled'
ORDER BY t."case_id", t."language",
         CASE
             WHEN t."document_kind" IN ('summary', 'information', 'oj_notice') THEN 2
             WHEN t."document_kind" = 'extract' THEN 1
             ELSE 0
         END,
         (t."fulltext" IS NULL OR btrim(t."fulltext") = ''),
         CASE t."source"
             WHEN 'RECHTSPRAAK' THEN 1
             WHEN 'HUDOC' THEN 2
             WHEN 'CELLAR_ITEM' THEN 3
             WHEN 'INFOCURIA_BLOB_HTML' THEN 4
             ELSE 5
         END,
         t."id";

-- ---- 0009_cross_dataset_links.sql ----
-- Cross-dataset links: provenance, identifiers and the tables later phases fill.
--
-- Design: cjeu-migration docs/LINKING_DESIGN.md (Phase 1 of
-- docs/CROSS_DATASET_ROADMAP.md). Strictly additive:
--
--   * case_citation gains four nullable columns (no default, so existing rows
--     are not rewritten) and two NOT VALID checks on them (no scan of existing
--     rows; enforced for new and updated rows).
--   * Everything else is a new, empty table. Nothing reads them until the code
--     that fills them ships, and none of them feeds a count or an API response.
--
-- Indexes on case_citation itself are in 0010, a separate file: the migrator
-- applies each file in one transaction, so an index built here would scan
-- case_citation while still holding the ACCESS EXCLUSIVE lock that ADD COLUMN
-- takes, blocking every API read for the length of the scan. This file holds
-- that lock only for the catalogue changes.

-- (migration only) SET LOCAL lock_timeout = '5s';

-- ---------------------------------------------------------------------------
-- case_citation: how each link was found (R1.1)
-- ---------------------------------------------------------------------------

ALTER TABLE "cle_v2"."case_citation"
    ADD COLUMN IF NOT EXISTS "match_method" text,
    ADD COLUMN IF NOT EXISTS "confidence" real,
    ADD COLUMN IF NOT EXISTS "target_ref_raw" text,
    ADD COLUMN IF NOT EXISTS "target_ref_scheme" text;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
         WHERE conrelid = '"cle_v2"."case_citation"'::regclass
           AND conname = 'case_citation_confidence_check'
    ) THEN
        ALTER TABLE "cle_v2"."case_citation"
            ADD CONSTRAINT "case_citation_confidence_check"
            CHECK ("confidence" IS NULL OR "confidence" BETWEEN 0 AND 1) NOT VALID;
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
         WHERE conrelid = '"cle_v2"."case_citation"'::regclass
           AND conname = 'case_citation_target_ref_scheme_check'
    ) THEN
        ALTER TABLE "cle_v2"."case_citation"
            ADD CONSTRAINT "case_citation_target_ref_scheme_check"
            CHECK ("target_ref_raw" IS NULL OR "target_ref_scheme" IS NOT NULL) NOT VALID;
    END IF;
END
$$;

COMMENT ON COLUMN "cle_v2"."case_citation"."match_method" IS
    'How the target was found: ecli | celex | case_number | appno | ljn | zaaknummer | metadata | formal_relation | name_date. NULL on rows loaded before 0009.';
COMMENT ON COLUMN "cle_v2"."case_citation"."confidence" IS
    'The extractor''s own estimate that the link is right, 0 to 1. NULL on rows loaded before 0009.';
COMMENT ON COLUMN "cle_v2"."case_citation"."target_ref_raw" IS
    'The cited reference, normalised, when it is not an ECLI or CELEX (a CJEU case number, an ECtHR application number, a Dutch case number). The text as written is in case_citation_mention.raw_text.';
COMMENT ON COLUMN "cle_v2"."case_citation"."target_ref_scheme" IS
    'Scheme of target_ref_raw: cjeu_case_number | echr_appno | nl_zaaknummer | ljn | name_date. Required when target_ref_raw is set.';

-- ---------------------------------------------------------------------------
-- case_citation_mention: every place a link occurs (R1.1, R1.3)
-- ---------------------------------------------------------------------------
-- case_citation keeps one row per (source, target, relation, dataset); a
-- judgment often cites the same case in several paragraphs. Each occurrence is
-- a row here, with where it is and, later, how the court treats it (R5.4).

CREATE TABLE IF NOT EXISTS "cle_v2"."case_citation_mention" (
    "id" bigint GENERATED ALWAYS AS IDENTITY,
    "citation_id" bigint NOT NULL,
    "case_text_id" bigint,
    "text_field" text NOT NULL,             -- fulltext | summary | national_judgement_xml | metadata
    "language" text,
    "char_start" int,                       -- offsets into the text as stored when extracted
    "char_end" int,
    "raw_text" text NOT NULL,               -- the reference as written
    "context" text,                         -- up to ~300 characters around it
    "segment_id" bigint,
    "section" text,                         -- e.g. the ECtHR part quoting domestic law (decision D4)
    "treatment_label" text,                 -- follows | applies | distinguishes | departs_from (R5.4)
    "treatment_model" text,
    "treatment_confidence" real,
    "extractor_version" text NOT NULL,
    "created_at" timestamptz DEFAULT now() NOT NULL,
    PRIMARY KEY ("id"),
    CONSTRAINT "case_citation_mention_treatment_confidence_check"
        CHECK ("treatment_confidence" IS NULL OR "treatment_confidence" BETWEEN 0 AND 1),
    CONSTRAINT "fk_case_citation_mention_citation" FOREIGN KEY ("citation_id")
        REFERENCES "cle_v2"."case_citation" ("id") ON DELETE CASCADE,
    CONSTRAINT "fk_case_citation_mention_case_text" FOREIGN KEY ("case_text_id")
        REFERENCES "cle_v2"."case_text" ("id") ON DELETE SET NULL,
    CONSTRAINT "fk_case_citation_mention_segment" FOREIGN KEY ("segment_id")
        REFERENCES "cle_v2"."case_segment" ("id") ON DELETE SET NULL
);
CREATE UNIQUE INDEX IF NOT EXISTS "case_citation_mention_uk" ON "cle_v2"."case_citation_mention"
    ("citation_id", "text_field", COALESCE("language", ''), COALESCE("char_start", -1), md5("raw_text"));
CREATE INDEX IF NOT EXISTS "case_citation_mention_idx_segment"
    ON "cle_v2"."case_citation_mention" ("segment_id") WHERE "segment_id" IS NOT NULL;
CREATE INDEX IF NOT EXISTS "case_citation_mention_idx_case_text"
    ON "cle_v2"."case_citation_mention" ("case_text_id") WHERE "case_text_id" IS NOT NULL;

-- ---------------------------------------------------------------------------
-- case_identifier: every identifier a case is cited by (R1.2)
-- ---------------------------------------------------------------------------
-- Not unique on (scheme, value_normalized): a CJEU case number belongs to the
-- judgment, its orders and the Advocate General's opinion, an application
-- number to several ECtHR documents. Extractors choose among them and record
-- how in case_citation.match_method / confidence. value_normalized follows
-- case-law-explorer data_extraction/linking/identifiers.py.

CREATE TABLE IF NOT EXISTS "cle_v2"."case_identifier" (
    "id" bigint GENERATED ALWAYS AS IDENTITY,
    "case_id" bigint NOT NULL,
    "scheme" text NOT NULL,                 -- ecli | ljn | celex | cjeu_case_number | echr_appno | nl_zaaknummer | cellar_dossier_uuid
    "value" text NOT NULL,                  -- as found
    "value_normalized" text NOT NULL,
    "source" text NOT NULL,                 -- where it was found, e.g. cjeu_document.case_number, cellar_joins, echr_document_appno
    "is_primary" boolean DEFAULT false NOT NULL,
    "created_at" timestamptz DEFAULT now() NOT NULL,
    PRIMARY KEY ("id"),
    CONSTRAINT "fk_case_identifier_case" FOREIGN KEY ("case_id")
        REFERENCES "cle_v2"."cases" ("id") ON DELETE CASCADE
);
CREATE UNIQUE INDEX IF NOT EXISTS "case_identifier_uk"
    ON "cle_v2"."case_identifier" ("case_id", "scheme", "value_normalized");
CREATE INDEX IF NOT EXISTS "case_identifier_idx_lookup"
    ON "cle_v2"."case_identifier" ("scheme", "value_normalized");
CREATE INDEX IF NOT EXISTS "case_identifier_idx_value_trgm"
    ON "cle_v2"."case_identifier" USING gin ("value_normalized" gin_trgm_ops);

-- ---------------------------------------------------------------------------
-- What each relation type and each source dataset is (documentation lookups)
-- ---------------------------------------------------------------------------
-- No foreign keys: existing rows stay as they are. Seeded in 0010 from the
-- values actually present in case_citation, so nothing is guessed. Nothing
-- reads these tables until the count and API guard (a later, separate change)
-- does, and that guard keeps every dataset present today counted, so it
-- changes no number on its own.

CREATE TABLE IF NOT EXISTS "cle_v2"."citation_relation_type" (
    "code" text NOT NULL,
    "description" text NOT NULL,
    "is_citation" boolean NOT NULL,         -- a decision relying on another decision
    "is_inverse" boolean DEFAULT false NOT NULL,  -- stored from the target's side (Cellar cited_by)
    "is_identity" boolean DEFAULT false NOT NULL, -- the same decision under another identifier
    "counted" boolean NOT NULL,             -- meant for citation counts once correct counts (R1.4) land
    PRIMARY KEY ("code")
);

CREATE TABLE IF NOT EXISTS "cle_v2"."citation_source_dataset" (
    "code" text NOT NULL,
    "description" text NOT NULL,
    "corpus" text,                          -- RS | CJEU | ECHR | cross
    "counted" boolean DEFAULT false NOT NULL,
    "active_in_api" boolean DEFAULT false NOT NULL,
    PRIMARY KEY ("code")
);

INSERT INTO "cle_v2"."citation_relation_type"
    ("code", "description", "is_citation", "is_inverse", "is_identity", "counted")
VALUES
    ('cites', 'The source decision cites the target decision.', true, false, false, true),
    ('cited_by', 'Stored from the cited side: the target decision cites the source (Cellar).', true, true, false, false),
    ('joins', 'Joined cases (Cellar).', false, false, false, false),
    ('is_about_concept', 'Subject-matter concept, not a decision (Cellar).', false, false, false, false),
    ('subject_to_appeal', 'The decision was appealed (Cellar).', false, false, false, false),
    ('reexamined_by', 'The decision was reviewed (Cellar).', false, false, false, false),
    ('referred_for_preliminary_ruling', 'Reference for a preliminary ruling (Cellar).', false, false, false, false),
    ('interprets_judgement', 'Interpretation of a judgment (Cellar).', true, false, false, true),
    ('logical_successor_of', 'Successor document (Cellar).', false, false, false, false),
    ('preliminary_reference', 'A national court''s referral to the CJEU ruling that answers it.', false, false, false, false),
    ('national_follow_up', 'A national decision given after, and applying, a CJEU ruling.', true, false, false, true),
    ('opinion_of', 'An Advocate General''s opinion to the judgment it was delivered in.', false, false, false, false),
    ('appeal_of', 'A CJEU appeal judgment to the General Court decision under appeal.', false, false, false, false),
    ('earlier_instance', 'A decision to an earlier decision in the same national proceedings.', false, false, false, false)
ON CONFLICT ("code") DO NOTHING;

-- ---------------------------------------------------------------------------
-- Other cited authorities (Phase 4): parliamentary papers, policy rules,
-- EU preparatory acts, foreign and EFTA courts, treaty bodies, literature
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS "cle_v2"."authority_document" (
    "id" bigint GENERATED ALWAYS AS IDENTITY,
    "kind" text NOT NULL,                   -- nl_parliamentary_paper | nl_policy_rule | eu_preparatory_act | national_court_decision | efta_court | un_treaty_body | coe_body | literature
    "identifier" text,
    "identifier_scheme" text,
    "title" text,
    "issuer" text,
    "date" date,
    "url" text,
    "created_at" timestamptz DEFAULT now() NOT NULL,
    PRIMARY KEY ("id")
);
CREATE UNIQUE INDEX IF NOT EXISTS "authority_document_uk" ON "cle_v2"."authority_document"
    ("kind", COALESCE("identifier_scheme", ''), "identifier") WHERE "identifier" IS NOT NULL;

CREATE TABLE IF NOT EXISTS "cle_v2"."case_authority_reference" (
    "id" bigint GENERATED ALWAYS AS IDENTITY,
    "case_id" bigint NOT NULL,
    "authority_document_id" bigint,
    "raw_reference" text NOT NULL,
    "pinpoint" text,
    "text_field" text,
    "language" text,
    "char_start" int,
    "char_end" int,
    "context_segment_id" bigint,
    "source_dataset" text NOT NULL,
    "extractor_version" text NOT NULL,
    "match_method" text,
    "confidence" real,
    "created_at" timestamptz DEFAULT now() NOT NULL,
    PRIMARY KEY ("id"),
    CONSTRAINT "case_authority_reference_confidence_check"
        CHECK ("confidence" IS NULL OR "confidence" BETWEEN 0 AND 1),
    CONSTRAINT "fk_case_authority_reference_case" FOREIGN KEY ("case_id")
        REFERENCES "cle_v2"."cases" ("id") ON DELETE CASCADE,
    CONSTRAINT "fk_case_authority_reference_document" FOREIGN KEY ("authority_document_id")
        REFERENCES "cle_v2"."authority_document" ("id") ON DELETE SET NULL,
    CONSTRAINT "fk_case_authority_reference_segment" FOREIGN KEY ("context_segment_id")
        REFERENCES "cle_v2"."case_segment" ("id") ON DELETE SET NULL
);
CREATE UNIQUE INDEX IF NOT EXISTS "case_authority_reference_uk" ON "cle_v2"."case_authority_reference"
    ("case_id", "raw_reference", COALESCE("text_field", ''), COALESCE("char_start", -1), "source_dataset");
CREATE INDEX IF NOT EXISTS "case_authority_reference_idx_document" ON "cle_v2"."case_authority_reference"
    ("authority_document_id") WHERE "authority_document_id" IS NOT NULL;
CREATE INDEX IF NOT EXISTS "case_authority_reference_idx_segment" ON "cle_v2"."case_authority_reference"
    ("context_segment_id") WHERE "context_segment_id" IS NOT NULL;
CREATE INDEX IF NOT EXISTS "case_authority_reference_idx_dataset" ON "cle_v2"."case_authority_reference"
    ("source_dataset");

-- ---------------------------------------------------------------------------
-- Outcomes and status (Phase 5)
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS "cle_v2"."case_outcome" (
    "id" bigint GENERATED ALWAYS AS IDENTITY,
    "case_id" bigint NOT NULL,
    "scope" text DEFAULT 'overall' NOT NULL, -- overall | article
    "article" text,                         -- ECtHR: '3', '8', 'P1-1'
    "outcome" text NOT NULL,                -- violation | no_violation | dismissed | upheld | quashed | inadmissible | annulled | answered | ...
    "raw_value" text,
    "source_dataset" text NOT NULL,
    "extractor_version" text NOT NULL,
    "created_at" timestamptz DEFAULT now() NOT NULL,
    PRIMARY KEY ("id"),
    CONSTRAINT "fk_case_outcome_case" FOREIGN KEY ("case_id")
        REFERENCES "cle_v2"."cases" ("id") ON DELETE CASCADE
);
CREATE UNIQUE INDEX IF NOT EXISTS "case_outcome_uk" ON "cle_v2"."case_outcome"
    ("case_id", "scope", COALESCE("article", ''), "outcome", "source_dataset");

CREATE TABLE IF NOT EXISTS "cle_v2"."case_status" (
    "id" bigint GENERATED ALWAYS AS IDENTITY,
    "case_id" bigint NOT NULL,
    "status" text NOT NULL,                 -- pending | struck_out | referred_to_grand_chamber | final | overturned
    "status_date" date,
    "related_case_id" bigint,
    "raw_value" text,
    "source_dataset" text NOT NULL,
    "extractor_version" text NOT NULL,
    "created_at" timestamptz DEFAULT now() NOT NULL,
    PRIMARY KEY ("id"),
    CONSTRAINT "fk_case_status_case" FOREIGN KEY ("case_id")
        REFERENCES "cle_v2"."cases" ("id") ON DELETE CASCADE,
    CONSTRAINT "fk_case_status_related" FOREIGN KEY ("related_case_id")
        REFERENCES "cle_v2"."cases" ("id") ON DELETE SET NULL
);
CREATE UNIQUE INDEX IF NOT EXISTS "case_status_uk" ON "cle_v2"."case_status"
    ("case_id", "status", COALESCE("status_date", '-infinity'::date), "source_dataset");
CREATE INDEX IF NOT EXISTS "case_status_idx_related" ON "cle_v2"."case_status"
    ("related_case_id") WHERE "related_case_id" IS NOT NULL;

-- ---------------------------------------------------------------------------
-- For the ECtHR edge rebuild (roadmap R6.1). Empty until its gate has passed
-- and the owner has approved it; nothing here touches existing rows.
-- ---------------------------------------------------------------------------

-- Same columns and defaults as case_citation, not its identity, indexes,
-- foreign keys or triggers: archived rows keep their original id and nothing
-- fires. Archive and restore list their columns explicitly.
CREATE TABLE IF NOT EXISTS "cle_v2"."case_citation_archive"
    (LIKE "cle_v2"."case_citation" INCLUDING DEFAULTS);
ALTER TABLE "cle_v2"."case_citation_archive"
    ADD COLUMN IF NOT EXISTS "archived_at" timestamptz DEFAULT now() NOT NULL,
    ADD COLUMN IF NOT EXISTS "archive_reason" text NOT NULL,
    ADD COLUMN IF NOT EXISTS "archive_batch" text NOT NULL;
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
         WHERE conrelid = '"cle_v2"."case_citation_archive"'::regclass AND contype = 'p'
    ) THEN
        ALTER TABLE "cle_v2"."case_citation_archive"
            ADD CONSTRAINT "case_citation_archive_pkey" PRIMARY KEY ("archive_batch", "id");
    END IF;
END
$$;

-- Corrected ECtHR edges, built and reviewed before anything is swapped.
-- Natural keys only, so it can be built on db-dev and replayed.
CREATE TABLE IF NOT EXISTS "cle_v2"."echr_edge_v2_staging" (
    "id" bigint GENERATED ALWAYS AS IDENTITY,
    "source_ecli" text,
    "source_item_id" text,
    "target_ecli" text,
    "target_item_id" text,
    "scl_reference" text NOT NULL,          -- the HUDOC scl entry the edge comes from
    "appno" text,
    "rule" text NOT NULL,                   -- which disambiguation rule chose the target
    "build_version" text NOT NULL,
    "created_at" timestamptz DEFAULT now() NOT NULL,
    PRIMARY KEY ("id"),
    CONSTRAINT "echr_edge_v2_staging_source_check"
        CHECK ("source_ecli" IS NOT NULL OR "source_item_id" IS NOT NULL)
);
CREATE UNIQUE INDEX IF NOT EXISTS "echr_edge_v2_staging_uk" ON "cle_v2"."echr_edge_v2_staging"
    (COALESCE("source_ecli", "source_item_id"), COALESCE("target_ecli", "target_item_id", ''),
     "scl_reference", "build_version");
CREATE INDEX IF NOT EXISTS "echr_edge_v2_staging_idx_source"
    ON "cle_v2"."echr_edge_v2_staging" ("build_version", "source_ecli");
CREATE INDEX IF NOT EXISTS "echr_edge_v2_staging_idx_target"
    ON "cle_v2"."echr_edge_v2_staging" ("build_version", "target_ecli") WHERE "target_ecli" IS NOT NULL;

-- ---------------------------------------------------------------------------
-- Correct citation counts, set-based (R1.4). Created here, called by nothing:
-- switching counts over is a separate change with a before/after report.
-- ---------------------------------------------------------------------------
-- For the given cases (all cases when NULL): cites_count = distinct cases
-- cited, cited_by_count = distinct citing cases, from resolved rows only,
-- leaving out self-loops and relation types and datasets marked not counted.
-- Types and datasets missing from the lookups count, so no value disappears
-- silently. Cases with no counted link are set to 0 (rows are created only
-- for cases with a count or an existing row).

CREATE OR REPLACE FUNCTION "cle_v2"."refresh_case_citation_counts"(p_case_ids bigint[] DEFAULT NULL)
RETURNS integer
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = "cle_v2"
AS $$
DECLARE
    changed integer;
BEGIN
    WITH scope AS (
        SELECT c.id AS case_id
          FROM cases c
         WHERE p_case_ids IS NULL
        UNION
        SELECT DISTINCT u.case_id
          FROM unnest(p_case_ids) AS u(case_id)
          JOIN cases c ON c.id = u.case_id
         WHERE p_case_ids IS NOT NULL
    ),
    counted AS NOT MATERIALIZED (
        SELECT cc.source_case_id, cc.target_case_id
          FROM case_citation cc
          LEFT JOIN citation_relation_type rt ON rt.code = cc.relation_type
          LEFT JOIN citation_source_dataset sd ON sd.code = cc.source_dataset
         WHERE cc.source_case_id IS NOT NULL
           AND cc.target_case_id IS NOT NULL
           AND cc.source_case_id <> cc.target_case_id
           AND COALESCE(rt.counted, true)
           AND COALESCE(sd.counted, true)
    ),
    cites AS (
        SELECT s.case_id, count(DISTINCT k.target_case_id)::int AS n
          FROM scope s JOIN counted k ON k.source_case_id = s.case_id
         GROUP BY s.case_id
    ),
    cited AS (
        SELECT s.case_id, count(DISTINCT k.source_case_id)::int AS n
          FROM scope s JOIN counted k ON k.target_case_id = s.case_id
         GROUP BY s.case_id
    ),
    fresh AS (
        SELECT s.case_id,
               COALESCE(ci.n, 0) AS cites_count,
               COALESCE(cb.n, 0) AS cited_by_count
          FROM scope s
          LEFT JOIN cites ci ON ci.case_id = s.case_id
          LEFT JOIN cited cb ON cb.case_id = s.case_id
    ),
    upserted AS (
        INSERT INTO case_citation_counts AS cnt (case_id, cites_count, cited_by_count, updated_at)
        SELECT f.case_id, f.cites_count, f.cited_by_count, now()
          FROM fresh f
         WHERE f.cites_count > 0
            OR f.cited_by_count > 0
            OR EXISTS (SELECT 1 FROM case_citation_counts x WHERE x.case_id = f.case_id)
        ON CONFLICT (case_id) DO UPDATE
           SET cites_count = EXCLUDED.cites_count,
               cited_by_count = EXCLUDED.cited_by_count,
               updated_at = now()
         WHERE cnt.cites_count IS DISTINCT FROM EXCLUDED.cites_count
            OR cnt.cited_by_count IS DISTINCT FROM EXCLUDED.cited_by_count
        RETURNING 1
    )
    SELECT count(*) INTO changed FROM upserted;
    RETURN changed;
END;
$$;

REVOKE ALL ON FUNCTION "cle_v2"."refresh_case_citation_counts"(bigint[]) FROM PUBLIC;

-- ---- 0010_case_citation_link_indexes.sql ----
-- Indexes on case_citation for the cross-dataset link columns of 0009, and
-- the lookups seeded from the data.
--
-- A separate file from 0009 on purpose: the migrator applies each file in one
-- transaction, and here no ALTER TABLE precedes the index builds, so each build
-- takes only a SHARE lock on case_citation. API reads continue; writes to
-- case_citation wait for the scans. Apply outside the Monday ETL and Thursday
-- promotion windows.
--
--   case_citation_uk_unresolved_ref   idempotent unresolved rows referenced by
--                                     case number / application number, like
--                                     the existing _uk_unresolved_ecli/_celex
--   case_citation_idx_target_ref      late-binding resolution (roadmap R2.9)
--                                     looks rows up by reference
--   case_citation_idx_source_dataset  one-statement removal of a dataset, and
--                                     per-dataset verification counts
--
-- The two partial indexes cover no existing row (target_ref_raw is new and
-- NULL everywhere), but building them still reads the table once each.

-- (migration only) SET LOCAL lock_timeout = '5s';

CREATE UNIQUE INDEX IF NOT EXISTS "case_citation_uk_unresolved_ref" ON "cle_v2"."case_citation"
    ("source_case_id", "target_ref_scheme", "target_ref_raw", COALESCE("relation_type", ''), "source_dataset")
    WHERE "target_case_id" IS NULL AND "target_ref_raw" IS NOT NULL;

CREATE INDEX IF NOT EXISTS "case_citation_idx_target_ref" ON "cle_v2"."case_citation"
    ("target_ref_scheme", "target_ref_raw")
    WHERE "target_case_id" IS NULL AND "target_ref_raw" IS NOT NULL;

CREATE INDEX IF NOT EXISTS "case_citation_idx_source_dataset" ON "cle_v2"."case_citation"
    ("source_dataset");

-- Every dataset and relation type present today, as found in the data rather
-- than listed by hand. Datasets present today are marked counted and active in
-- the API, which is what they are now; datasets added later start as neither.
-- Relation types not described in 0009 are recorded as counted citations,
-- which is how every count treats them today.

INSERT INTO "cle_v2"."citation_source_dataset" ("code", "description", "corpus", "counted", "active_in_api")
SELECT d."source_dataset",
       'Present when migration 0010 ran.',
       CASE
           WHEN d."source_dataset" LIKE 'rs\_%' OR d."source_dataset" LIKE 'lido%' THEN 'RS'
           WHEN d."source_dataset" LIKE 'cellar%' OR d."source_dataset" LIKE 'cjeu%' THEN 'CJEU'
           WHEN d."source_dataset" LIKE 'echr%' THEN 'ECHR'
       END,
       true,
       true
  FROM (SELECT DISTINCT "source_dataset" FROM "cle_v2"."case_citation") d
ON CONFLICT ("code") DO NOTHING;

INSERT INTO "cle_v2"."citation_relation_type"
    ("code", "description", "is_citation", "is_inverse", "is_identity", "counted")
SELECT r."relation_type",
       'Present when migration 0010 ran; not yet described.',
       true, false, false, true
  FROM (SELECT DISTINCT "relation_type" FROM "cle_v2"."case_citation"
         WHERE "relation_type" IS NOT NULL) r
ON CONFLICT ("code") DO NOTHING;
