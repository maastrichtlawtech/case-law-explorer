CREATE SCHEMA "public";
CREATE SCHEMA "cle_v2";
CREATE SCHEMA "legacy";
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
	"jc_id" text CONSTRAINT "legal_provision_jc_id_key" UNIQUE,
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
	"jc_id" text CONSTRAINT "legislation_jc_id_key" UNIQUE,
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
CREATE UNIQUE INDEX "_lang_map_pkey" ON "cle_v2"."_lang_map" ("hudoc");
CREATE INDEX "case_citation_idx_relation_type" ON "cle_v2"."case_citation" ("relation_type");
CREATE INDEX "case_citation_idx_source" ON "cle_v2"."case_citation" ("source_case_id");
CREATE INDEX "case_citation_idx_source_target" ON "cle_v2"."case_citation" ("source_case_id","target_case_id");
CREATE INDEX "case_citation_idx_target" ON "cle_v2"."case_citation" ("target_case_id");
CREATE INDEX "case_citation_idx_target_celex_raw" ON "cle_v2"."case_citation" ("target_celex_raw");
CREATE INDEX "case_citation_idx_target_ecli_raw" ON "cle_v2"."case_citation" ("target_ecli_raw");
CREATE INDEX "case_citation_idx_weight" ON "cle_v2"."case_citation" ("weight");
CREATE UNIQUE INDEX "case_citation_pkey" ON "cle_v2"."case_citation" ("id");
CREATE UNIQUE INDEX "case_citation_uk_resolved" ON "cle_v2"."case_citation" ("source_case_id","target_case_id","relation_type","source_dataset");
CREATE UNIQUE INDEX "case_citation_uk_unresolved_celex" ON "cle_v2"."case_citation" ("source_case_id","target_celex_raw","relation_type","source_dataset");
CREATE UNIQUE INDEX "case_citation_uk_unresolved_ecli" ON "cle_v2"."case_citation" ("source_case_id","target_ecli_raw","relation_type","source_dataset");
CREATE UNIQUE INDEX "case_citation_counts_pkey" ON "cle_v2"."case_citation_counts" ("case_id");
CREATE UNIQUE INDEX "case_cluster_pkey" ON "cle_v2"."case_cluster" ("id");
CREATE UNIQUE INDEX "case_cluster_membership_pkey" ON "cle_v2"."case_cluster_membership" ("cluster_id","case_id");
CREATE INDEX "case_domain_idx_domain_id" ON "cle_v2"."case_domain" ("domain_id");
CREATE UNIQUE INDEX "case_domain_pkey" ON "cle_v2"."case_domain" ("case_id","domain_id");
CREATE INDEX "case_entity_idx_case_id" ON "cle_v2"."case_entity" ("case_id");
CREATE UNIQUE INDEX "case_entity_pkey" ON "cle_v2"."case_entity" ("id");
CREATE UNIQUE INDEX "case_judge_case_id_judge_id_role_key" ON "cle_v2"."case_judge" ("case_id","judge_id","role");
CREATE INDEX "case_judge_idx_case_id" ON "cle_v2"."case_judge" ("case_id");
CREATE INDEX "case_judge_idx_judge_id" ON "cle_v2"."case_judge" ("judge_id");
CREATE UNIQUE INDEX "case_judge_pkey" ON "cle_v2"."case_judge" ("id");
CREATE INDEX "case_law_reference_idx_case_id" ON "cle_v2"."case_law_reference" ("case_id");
CREATE INDEX "case_law_reference_idx_legislation" ON "cle_v2"."case_law_reference" ("legislation_id");
CREATE INDEX "case_law_reference_idx_provision" ON "cle_v2"."case_law_reference" ("provision_id");
CREATE INDEX "case_law_reference_idx_raw" ON "cle_v2"."case_law_reference" ("raw_scheme","raw_resource");
CREATE INDEX "case_law_reference_idx_raw_label" ON "cle_v2"."case_law_reference" ("raw_label_id");
CREATE UNIQUE INDEX "case_law_reference_pkey" ON "cle_v2"."case_law_reference" ("id");
CREATE UNIQUE INDEX "case_law_reference_uk_legislation" ON "cle_v2"."case_law_reference" ("case_id","legislation_id","role","source_dataset");
CREATE UNIQUE INDEX "case_law_reference_uk_provision" ON "cle_v2"."case_law_reference" ("case_id","provision_id","role","source_dataset");
CREATE UNIQUE INDEX "case_law_reference_uk_raw" ON "cle_v2"."case_law_reference" ("case_id","raw_scheme","raw_resource","COALESCE(raw_subdivision, ''::text)","role","source_dataset");
CREATE INDEX "case_network_metric_idx_case" ON "cle_v2"."case_network_metric" ("case_id");
CREATE UNIQUE INDEX "case_network_metric_pkey" ON "cle_v2"."case_network_metric" ("snapshot_id","case_id");
CREATE INDEX "case_party_idx_party" ON "cle_v2"."case_party" ("party_id");
CREATE UNIQUE INDEX "case_party_pkey" ON "cle_v2"."case_party" ("case_id","party_id","role","ordinal");
CREATE UNIQUE INDEX "case_segment_case_id_segment_hash_key" ON "cle_v2"."case_segment" ("case_id","segment_hash");
CREATE INDEX "case_segment_idx_case_id" ON "cle_v2"."case_segment" ("case_id");
CREATE UNIQUE INDEX "case_segment_pkey" ON "cle_v2"."case_segment" ("id");
CREATE INDEX "case_summary_version_idx_case" ON "cle_v2"."case_summary_version" ("case_id");
CREATE UNIQUE INDEX "case_summary_version_pkey" ON "cle_v2"."case_summary_version" ("id");
CREATE UNIQUE INDEX "case_summary_version_uk_current" ON "cle_v2"."case_summary_version" ("case_id","segment_scope","summarization_model");
CREATE UNIQUE INDEX "case_text_case_id_language_source_key" ON "cle_v2"."case_text" ("case_id","language","source");
CREATE INDEX "case_text_idx_case_id" ON "cle_v2"."case_text" ("case_id");
CREATE INDEX "case_text_idx_fulltext_tsv" ON "cle_v2"."case_text" USING gin ("fulltext_tsv");
CREATE INDEX "case_text_idx_stub" ON "cle_v2"."case_text" ("case_id");
CREATE INDEX "case_text_idx_summary_embedding" ON "cle_v2"."case_text" USING hnsw ("summary_embedding");
CREATE INDEX "case_text_idx_summary_tsv" ON "cle_v2"."case_text" USING gin ("summary_tsv");
CREATE UNIQUE INDEX "case_text_pkey" ON "cle_v2"."case_text" ("id");
CREATE INDEX "case_idx_case_number" ON "cle_v2"."cases" ("case_number");
CREATE INDEX "case_idx_case_number_trgm" ON "cle_v2"."cases" USING gin ("case_number");
CREATE INDEX "case_idx_court" ON "cle_v2"."cases" ("court_id");
CREATE INDEX "case_idx_date_decision" ON "cle_v2"."cases" ("date_decision");
CREATE INDEX "case_idx_date_ecli" ON "cle_v2"."cases" ("date_decision","ecli");
CREATE INDEX "case_idx_ecli" ON "cle_v2"."cases" ("ecli");
CREATE INDEX "case_idx_importance" ON "cle_v2"."cases" ("importance");
CREATE INDEX "case_idx_item_id" ON "cle_v2"."cases" ("item_id");
CREATE INDEX "case_idx_sources" ON "cle_v2"."cases" USING gin ("sources");
CREATE INDEX "case_idx_title_trgm" ON "cle_v2"."cases" USING gin ("title");
CREATE UNIQUE INDEX "cases_celex_id_key" ON "cle_v2"."cases" ("celex_id");
CREATE UNIQUE INDEX "cases_ecli_key" ON "cle_v2"."cases" ("ecli");
CREATE INDEX "cases_idx_case_number_btree" ON "cle_v2"."cases" ("case_number");
CREATE UNIQUE INDEX "cases_item_id_key" ON "cle_v2"."cases" ("item_id");
CREATE UNIQUE INDEX "cases_pkey" ON "cle_v2"."cases" ("id");
CREATE UNIQUE INDEX "cjeu_ag_opinion_case_id_key" ON "cle_v2"."cjeu_ag_opinion" ("case_id");
CREATE UNIQUE INDEX "cjeu_ag_opinion_pkey" ON "cle_v2"."cjeu_ag_opinion" ("id");
CREATE UNIQUE INDEX "cjeu_document_case_id_key" ON "cle_v2"."cjeu_document" ("case_id");
CREATE UNIQUE INDEX "cjeu_document_pkey" ON "cle_v2"."cjeu_document" ("id");
CREATE UNIQUE INDEX "cjeu_national_document_case_id_key" ON "cle_v2"."cjeu_national_document" ("case_id");
CREATE UNIQUE INDEX "cjeu_national_document_pkey" ON "cle_v2"."cjeu_national_document" ("id");
CREATE UNIQUE INDEX "court_code_key" ON "cle_v2"."court" ("code");
CREATE UNIQUE INDEX "court_pkey" ON "cle_v2"."court" ("id");
CREATE UNIQUE INDEX "court_formation_code_key" ON "cle_v2"."court_formation" ("code");
CREATE UNIQUE INDEX "court_formation_pkey" ON "cle_v2"."court_formation" ("id");
CREATE UNIQUE INDEX "document_type_code_key" ON "cle_v2"."document_type" ("code");
CREATE UNIQUE INDEX "document_type_pkey" ON "cle_v2"."document_type" ("id");
CREATE UNIQUE INDEX "domain_pkey" ON "cle_v2"."domain" ("id");
CREATE UNIQUE INDEX "domain_label_pkey" ON "cle_v2"."domain_label" ("domain_id","language");
CREATE INDEX "echr_document_idx_case_lang" ON "cle_v2"."echr_document" ("case_id","language");
CREATE INDEX "echr_document_idx_docname_trgm" ON "cle_v2"."echr_document" USING gin ("docname");
CREATE INDEX "echr_document_idx_doctype" ON "cle_v2"."echr_document" ("doctype");
CREATE INDEX "echr_document_idx_doctype_branch" ON "cle_v2"."echr_document" ("doctype_branch");
CREATE INDEX "echr_document_idx_issue_trgm" ON "cle_v2"."echr_document" USING gin ("issue");
CREATE INDEX "echr_document_idx_judgement_date" ON "cle_v2"."echr_document" ("judgement_date");
CREATE INDEX "echr_document_idx_judgement_year" ON "cle_v2"."echr_document" ("judgement_year");
CREATE INDEX "echr_document_idx_originating_body" ON "cle_v2"."echr_document" ("originating_body");
CREATE INDEX "echr_document_idx_reference_date" ON "cle_v2"."echr_document" ("reference_date");
CREATE UNIQUE INDEX "echr_document_pkey" ON "cle_v2"."echr_document" ("item_id");
CREATE INDEX "echr_document_appno_idx_appno" ON "cle_v2"."echr_document_appno" ("appno");
CREATE INDEX "echr_document_appno_idx_source" ON "cle_v2"."echr_document_appno" ("source");
CREATE UNIQUE INDEX "echr_document_appno_pkey" ON "cle_v2"."echr_document_appno" ("item_id","appno","source");
CREATE INDEX "echr_document_article_idx_filter" ON "cle_v2"."echr_document_article" ("kind","article_code");
CREATE UNIQUE INDEX "echr_document_article_pkey" ON "cle_v2"."echr_document_article" ("item_id","kind","article_code");
CREATE UNIQUE INDEX "echr_document_secondary_text_pkey" ON "cle_v2"."echr_document_secondary_text" ("item_id");
CREATE INDEX "echr_extractor_segments_idx_num_sections" ON "cle_v2"."echr_extractor_segments" ("num_sections");
CREATE INDEX "echr_extractor_segments_idx_parser" ON "cle_v2"."echr_extractor_segments" ("parser_mode");
CREATE UNIQUE INDEX "echr_extractor_segments_pkey" ON "cle_v2"."echr_extractor_segments" ("item_id");
CREATE UNIQUE INDEX "instance_code_key" ON "cle_v2"."instance" ("code");
CREATE UNIQUE INDEX "instance_pkey" ON "cle_v2"."instance" ("id");
CREATE UNIQUE INDEX "judge_pkey" ON "cle_v2"."judge" ("id");
CREATE UNIQUE INDEX "jurisdiction_iso_code_key" ON "cle_v2"."jurisdiction" ("iso_code");
CREATE UNIQUE INDEX "jurisdiction_pkey" ON "cle_v2"."jurisdiction" ("id");
CREATE UNIQUE INDEX "language_pkey" ON "cle_v2"."language" ("iso_code");
CREATE INDEX "legal_provision_idx_bwb_label" ON "cle_v2"."legal_provision" ("bwb_label_id");
CREATE INDEX "legal_provision_idx_lookup" ON "cle_v2"."legal_provision" ("legislation_id","lower(article_label)","element_type");
CREATE UNIQUE INDEX "legal_provision_jc_id_key" ON "cle_v2"."legal_provision" ("jc_id");
CREATE UNIQUE INDEX "legal_provision_lido_id_key" ON "cle_v2"."legal_provision" ("lido_id");
CREATE UNIQUE INDEX "legal_provision_pkey" ON "cle_v2"."legal_provision" ("id");
CREATE INDEX "legislation_idx_scheme_identifier" ON "cle_v2"."legislation" ("scheme","identifier");
CREATE UNIQUE INDEX "legislation_jc_id_key" ON "cle_v2"."legislation" ("jc_id");
CREATE UNIQUE INDEX "legislation_lido_id_key" ON "cle_v2"."legislation" ("lido_id");
CREATE UNIQUE INDEX "legislation_pkey" ON "cle_v2"."legislation" ("id");
CREATE INDEX "legislation_alias_idx_alias_lower" ON "cle_v2"."legislation_alias" ("lower(alias)");
CREATE INDEX "legislation_alias_idx_alias_trgm" ON "cle_v2"."legislation_alias" USING gin ("alias");
CREATE UNIQUE INDEX "legislation_alias_pkey" ON "cle_v2"."legislation_alias" ("id");
CREATE INDEX "lido_link_idx_source_case" ON "cle_v2"."lido_link" ("source_case_id");
CREATE INDEX "lido_link_idx_target_case" ON "cle_v2"."lido_link" ("target_case_id");
CREATE UNIQUE INDEX "lido_link_pkey" ON "cle_v2"."lido_link" ("id");
CREATE UNIQUE INDEX "migration_manifest_pkey" ON "cle_v2"."migration_manifest" ("step");
CREATE UNIQUE INDEX "network_snapshot_pkey" ON "cle_v2"."network_snapshot" ("id");
CREATE UNIQUE INDEX "party_pkey" ON "cle_v2"."party" ("id");
CREATE UNIQUE INDEX "procedure_type_code_key" ON "cle_v2"."procedure_type" ("code");
CREATE UNIQUE INDEX "procedure_type_pkey" ON "cle_v2"."procedure_type" ("id");
CREATE INDEX "rs_document_idx_date_decision" ON "cle_v2"."rs_document" ("date_decision");
CREATE INDEX "rs_document_idx_date_issued" ON "cle_v2"."rs_document" ("date_issued");
CREATE INDEX "rs_document_idx_date_modified" ON "cle_v2"."rs_document" ("date_modified");
CREATE INDEX "rs_document_idx_domains_gin" ON "cle_v2"."rs_document" USING gin ("domains");
CREATE UNIQUE INDEX "rs_document_pkey" ON "cle_v2"."rs_document" ("case_id");
CREATE UNIQUE INDEX "rs_document_external_authority_pkey" ON "cle_v2"."rs_document_external_authority" ("case_id","raw");
CREATE UNIQUE INDEX "rs_document_formal_relation_pkey" ON "cle_v2"."rs_document_formal_relation" ("case_id","target_identifier","relation_type","aanleg");
CREATE INDEX "rs_document_publication_idx_journal" ON "cle_v2"."rs_document_publication" ("journal_abbr");
CREATE UNIQUE INDEX "rs_document_publication_pkey" ON "cle_v2"."rs_document_publication" ("case_id","raw");
CREATE UNIQUE INDEX "search_query_log_pkey" ON "cle_v2"."search_query_log" ("id");
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
CREATE VIEW "cle_v2"."case_text_canonical" TABLESPACE cle_v2 AS (SELECT DISTINCT ON (case_id, language) id, case_id, language, fulltext, summary, summary_source, fulltext_tsv, summary_tsv, summary_embedding, embedding_model, source, text_format, missing_reasons, created_at, updated_at FROM cle_v2.case_text t ORDER BY case_id, language, ( CASE source WHEN 'RECHTSPRAAK'::text THEN 1 WHEN 'HUDOC'::text THEN 2 WHEN 'INFOCURIA_BLOB_HTML'::text THEN 3 WHEN 'CELLAR_ITEM'::text THEN 4 ELSE 5 END), id);
CREATE VIEW "cle_v2"."echr_v_document_with_text" TABLESPACE cle_v2 AS (SELECT d.item_id, d.case_id, d.language, d.extractedappno, d.docname, d.doctype, d.doctype_branch, d.judgement_date, d.reference_date, d.article, d.conclusion, d.violation, d.nonviolation, d.respondent, d.originating_body, d.represented_by, d.published_by, d.rules_of_court, d.applicability, d.separate_opinion, d.issue, d.importance, d.rank, d.scl, d.external_sources, d.judgement_year, d.created_at, d.updated_at, t.fulltext, t.fulltext_tsv FROM cle_v2.echr_document d LEFT JOIN cle_v2.case_text_canonical t ON t.case_id = d.case_id AND t.language = d.language);
CREATE VIEW "cle_v2"."echr_v_judgments_decisions" TABLESPACE cle_v2 AS (SELECT item_id, case_id, language, extractedappno, docname, doctype, doctype_branch, judgement_date, reference_date, article, conclusion, violation, nonviolation, respondent, originating_body, represented_by, published_by, rules_of_court, applicability, separate_opinion, issue, importance, rank, scl, external_sources, judgement_year, created_at, updated_at FROM cle_v2.echr_document WHERE doctype ~~* '%JUD%'::text OR doctype ~~* '%DEC%'::text);
CREATE VIEW "cle_v2"."rs_v_document_law_reference" TABLESPACE cle_v2 AS (SELECT r.case_id, c.ecli, r.raw_resource AS bwb_resource, COALESCE(r.raw_subdivision, ''::text) AS article, r.version_date, r.raw_label_id AS bwb_label_id, r.source_dataset AS source, r.raw_reference AS opschrift, ((('http://wetten.overheid.nl/id/'::text || r.raw_resource) || '/'::text) || COALESCE(cle_v2.rs_date_to_iso(r.version_date), '1900-01-01'::text)) || '/0'::text AS legal_provision_url, CASE WHEN r.raw_label_id IS NULL THEN NULL::text ELSE (((((('http://linkeddata.overheid.nl/terms/bwb/id/'::text || r.raw_resource) || '/'::text) || r.raw_label_id::text) || '/'::text) || COALESCE(cle_v2.rs_date_to_iso(r.version_date), '1900-01-01'::text)) || '/'::text) || COALESCE(cle_v2.rs_date_to_iso(r.version_date), '1900-01-01'::text) END AS legal_provision_url_lido FROM cle_v2.case_law_reference r JOIN cle_v2.cases c ON c.id = r.case_id WHERE r.raw_scheme = 'bwb'::text);
CREATE VIEW "cle_v2"."rs_v_document_legal_provisions" TABLESPACE cle_v2 AS (SELECT DISTINCT c.ecli, lr.raw_reference AS legal_provision FROM cle_v2.case_law_reference lr JOIN cle_v2.cases c ON c.id = lr.case_id WHERE lr.raw_scheme = 'bwb'::text AND NULLIF(lr.raw_reference, ''::text) IS NOT NULL UNION SELECT DISTINCT c.ecli, lp.title AS legal_provision FROM cle_v2.case_law_reference lr JOIN cle_v2.cases c ON c.id = lr.case_id JOIN cle_v2.legal_provision lp ON lp.bwb_label_id = lr.raw_label_id WHERE lr.raw_scheme = 'bwb'::text AND lr.raw_label_id IS NOT NULL AND NULLIF(lp.title, ''::text) IS NOT NULL UNION SELECT DISTINCT c.ecli, lp.title AS legal_provision FROM cle_v2.case_law_reference lr JOIN cle_v2.cases c ON c.id = lr.case_id JOIN cle_v2.legislation lg ON lg.scheme = 'bwb'::text AND lg.identifier = lr.raw_resource JOIN cle_v2.legal_provision lp ON lp.legislation_id = lg.id AND lower(lp.article_label) = lower(lr.raw_subdivision) AND lp.element_type = 'artikel'::text WHERE lr.raw_scheme = 'bwb'::text AND NULLIF(lp.title, ''::text) IS NOT NULL UNION SELECT DISTINCT c.ecli, lg.title AS legal_provision FROM cle_v2.case_law_reference lr JOIN cle_v2.cases c ON c.id = lr.case_id JOIN cle_v2.legislation lg ON lg.scheme = 'bwb'::text AND lg.identifier = lr.raw_resource WHERE lr.raw_scheme = 'bwb'::text AND NULLIF(lg.title, ''::text) IS NOT NULL UNION SELECT DISTINCT c.ecli, (lg.title || ', Artikel '::text) || lr.raw_subdivision AS legal_provision FROM cle_v2.case_law_reference lr JOIN cle_v2.cases c ON c.id = lr.case_id JOIN cle_v2.legislation lg ON lg.scheme = 'bwb'::text AND lg.identifier = lr.raw_resource WHERE lr.raw_scheme = 'bwb'::text AND NULLIF(lg.title, ''::text) IS NOT NULL AND NULLIF(lr.raw_subdivision, ''::text) IS NOT NULL UNION SELECT DISTINCT c.ecli, (lg.title || ', Bijlage '::text) || lr.raw_subdivision AS legal_provision FROM cle_v2.case_law_reference lr JOIN cle_v2.cases c ON c.id = lr.case_id JOIN cle_v2.legislation lg ON lg.scheme = 'bwb'::text AND lg.identifier = lr.raw_resource WHERE lr.raw_scheme = 'bwb'::text AND NULLIF(lg.title, ''::text) IS NOT NULL AND NULLIF(lr.raw_subdivision, ''::text) IS NOT NULL AND lr.raw_reference ~~* '%bijlage%'::text);
CREATE VIEW "cle_v2"."rs_v_document_with_text" TABLESPACE cle_v2 AS (SELECT d.case_id, d.date_decision, d.document_type, d.instance, d.domains, d.source, d.jurisdiction_country, d.procedure_type, d.url_publication, d.legal_provisions, d.predecessor_successor_cases, d.created_at, d.updated_at, d.date_published, d.date_issued, d.date_modified, d.title, d.language, d.access_rights, d.zittingsplaats, d.replaces_identifier, d.creator_uri, d.vindplaatsen, d.subject_uris, d.zaaknummer, d.opendata_status, t.summary, t.fulltext, t.fulltext_tsv FROM cle_v2.rs_document d LEFT JOIN cle_v2.case_text_canonical t ON t.case_id = d.case_id AND t.language = 'nl'::text);