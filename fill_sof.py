#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
fill_sof.py
- Coleta title+url de https://aps-repo.bvs.br/aps (117 páginas por padrão)
- Mantém/gera um CSV (default: sof.csv) com colunas: title,url,sof
- Para linhas com sof vazio, baixa o post e extrai TODO o corpo (sem truncar)

Melhorias:
- CSV sempre como string (sem NaN), aspas em tudo e \n como terminador.
- --only-index para só coletar índices (sem preencher o SOF).
- --no-index para usar somente as URLs já existentes no CSV.
- --limit N para testar em poucas linhas.
- --checkpoint-every N para salvar o CSV a cada N posts preenchidos.
- Sessão HTTP com retries e backoff leve.
"""

import re
import time
import sys
import csv
import argparse
from typing import List, Tuple, Optional, Set, Dict

import requests
from bs4 import BeautifulSoup, Tag
import pandas as pd
from tqdm import tqdm


BASE = "https://aps-repo.bvs.br"
LIST_ROOT = f"{BASE}/aps"
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

# ---- sessão HTTP com retries ------------------------------------------

def make_session() -> requests.Session:
    s = requests.Session()
    s.headers.update(HEADERS)
    try:
        from requests.adapters import HTTPAdapter
        from urllib3.util.retry import Retry  # type: ignore
        retry = Retry(
            total=4,
            connect=4,
            read=4,
            backoff_factor=0.6,
            status_forcelist=(429, 500, 502, 503, 504),
            allowed_methods=frozenset(["GET", "HEAD"]),
            raise_on_status=False,
        )
        adapter = HTTPAdapter(max_retries=retry)
        s.mount("http://", adapter)
        s.mount("https://", adapter)
    except Exception:
        # se urllib3 Retry não estiver disponível, segue sem
        pass
    return s

SESSION = make_session()

# ---- util --------------------------------------------------------------

def fetch(url: str, retries: int = 2, timeout: int = 30) -> Optional[str]:
    """GET com retries simples adicionais (além do adapter) e backoff leve."""
    last_err = None
    for i in range(retries + 1):
        try:
            r = SESSION.get(url, timeout=timeout)
            if r.status_code == 200 and r.text:
                return r.text
        except Exception as e:
            last_err = e
        time.sleep(0.8 + i * 0.7)
    if last_err:
        sys.stderr.write(f"[fetch] falhou: {url} -> {last_err}\n")
    else:
        sys.stderr.write(f"[fetch] status!=200: {url}\n")
    return None


def clean_spaces(s: str) -> str:
    if not s:
        return ""
    s = s.replace("\xa0", " ")
    s = re.sub(r"[ \t\r\f\v]+", " ", s)
    # normaliza quebras sem perder parágrafos
    s = re.sub(r"\n{3,}", "\n\n", s)
    return s.strip()


# ---- parsing do índice -------------------------------------------------

def parse_index_page(html: str) -> List[Tuple[str, str]]:
    """
    Encontra cards da listagem:
      <div class="card h-100 box1">
         <a href="POST_URL">
            <h5 class="card-title">TÍTULO</h5>
    """
    soup = BeautifulSoup(html, "html.parser")
    out: List[Tuple[str, str]] = []
    for card in soup.select("div.card.h-100.box1 a[href]"):
        url = (card.get("href") or "").strip()
        title_el = card.select_one(".card-title")
        title = title_el.get_text(strip=True) if title_el else ""
        if url and title:
            out.append((title, url))
    return out


def crawl_all_posts(max_pages: int = 117) -> List[Tuple[str, str]]:
    posts: List[Tuple[str, str]] = []
    seen: Set[str] = set()

    # página 1 (raiz)
    first = fetch(LIST_ROOT)
    if first:
        for t, u in parse_index_page(first):
            if u not in seen:
                seen.add(u)
                posts.append((t, u))

    # páginas 2..max_pages
    for p in tqdm(range(2, max_pages + 1), desc="Coletando índice"):
        url = f"{LIST_ROOT}/page/{p}/"
        html = fetch(url)
        if not html:
            continue
        for t, u in parse_index_page(html):
            if u not in seen:
                seen.add(u)
                posts.append((t, u))
        time.sleep(0.2)  # educado

    return posts


# ---- parsing do post (sof) --------------------------------------------

ALLOWED_NAMES = {"p", "figure", "ul", "ol", "table", "blockquote", "pre"}

def text_from_node(node: Tag) -> str:
    """
    Extrai texto amigável de um bloco (p/ figure/table/list/blockquote).
    Inclui ALT de imagens sem alterar o DOM.
    """
    # Coleta todos os ALT de imagens dentro do bloco
    alts = []
    try:
        for img in node.select("img[alt]"):
            alt = (img.get("alt") or "").strip()
            if alt:
                alts.append(alt)
    except Exception:
        pass

    # listas -> bullets
    if node.name in {"ul", "ol"}:
        items = []
        for li in node.find_all("li", recursive=True):
            t = li.get_text(" ", strip=True)
            if t:
                items.append(f"• {t}")
        base = "\n".join(items)
        if alts:
            base = (base + " " + " ".join(alts)).strip()
        return base

    # tabelas/figuras -> texto plano + ALT(s)
    if node.name in {"figure", "table"}:
        base = node.get_text(" ", strip=True)
        if alts:
            base = (base + " " + " ".join(alts)).strip()
        return base

    # padrão
    base = node.get_text(" ", strip=True)
    if alts:
        base = (base + " " + " ".join(alts)).strip()
    return base


def extract_sof(html: str) -> str:
    """
    Extrai TODO o corpo do post:
      - tudo entre o <hr> abaixo do bloco .small e o início da <div class="card"> (Bibliografia)
      - sem truncar no primeiro parágrafo/figure/tabela
    """
    soup = BeautifulSoup(html, "html.parser")

    container = soup.select_one("div.container.padding1")
    if not container:
        container = soup.body or soup

    # 1) acha o bloco de metadados (.small)
    meta = container.select_one("div.small")
    start = None
    if meta:
        hr = meta.find_next("hr")
        start = hr if hr else meta
    else:
        h1 = container.find("h1")
        hr = h1.find_next("hr") if h1 else None
        start = hr or h1 or container

    # 2) limite final: “Bibliografia Selecionada” fica dentro de <div class="card">
    end_card = container.find("div", class_=lambda c: c and "card" in c.split())

    # 3) varre irmãos até chegar no end_card
    parts: List[str] = []
    node = start.find_next_sibling() if isinstance(start, Tag) else None
    while node and node is not end_card:
        if isinstance(node, Tag):
            name = (node.name or "").lower()
            if name in ALLOWED_NAMES:
                try:
                    txt = text_from_node(node)
                    if txt:
                        parts.append(txt)
                except Exception as e:
                    sys.stderr.write(f"[extract_sof] bloco ignorado: {e}\n")
        node = node.find_next_sibling()

    # Fallback: se nada coletado (layout diferente), captura parágrafos do container
    if not parts:
        for p in container.find_all("p"):
            t = p.get_text(" ", strip=True)
            if t:
                parts.append(t)

    full = "\n\n".join([clean_spaces(p) for p in parts if p.strip()])
    return clean_spaces(full)


def extract_title_and_canonical(html: str, url_fetched: str) -> Tuple[str, str]:
    soup = BeautifulSoup(html, "html.parser")
    h1 = soup.find("h1")
    title = h1.get_text(" ", strip=True) if h1 else ""

    canon_el = soup.find("link", rel="canonical")
    canon = canon_el["href"].strip() if canon_el and canon_el.get("href") else url_fetched

    return title, canon


# ---- CSV + fluxo -------------------------------------------------------

def ensure_csv(path: str) -> pd.DataFrame:
    try:
        # evita NaN automáticos; tudo vira string
        df = pd.read_csv(path, dtype=str, keep_default_na=False)
    except FileNotFoundError:
        df = pd.DataFrame(columns=["title", "url", "sof"])
    # normaliza colunas
    for col in ["title", "url", "sof"]:
        if col not in df.columns:
            df[col] = ""
    # garante string
    df["title"] = df["title"].astype(str)
    df["url"] = df["url"].astype(str)
    df["sof"] = df["sof"].astype(str)
    return df


def merge_index_into_df(df: pd.DataFrame, index_posts: List[Tuple[str, str]]) -> pd.DataFrame:
    """
    Garante uma linha por URL do índice.
    Não sobrescreve title já existente; só preenche se vazio.
    """
    if df.empty:
        df = pd.DataFrame(index_posts, columns=["title", "url"])
        df["sof"] = ""
        return df

    existing_urls = set(df["url"].tolist())
    rows_to_add = []
    for title, url in index_posts:
        if url not in existing_urls:
            rows_to_add.append({"title": title, "url": url, "sof": ""})

    if rows_to_add:
        df = pd.concat([df, pd.DataFrame(rows_to_add)], ignore_index=True)

    # completa titles vazios com os do índice
    title_by_url: Dict[str, str] = {u: t for t, u in index_posts}
    mask_empty_title = (df["title"].str.strip() == "")
    df.loc[mask_empty_title, "title"] = (
        df.loc[mask_empty_title, "url"].map(title_by_url).fillna(df.loc[mask_empty_title, "title"])
    )
    return df


def fill_missing_sof(
    df: pd.DataFrame,
    limit: Optional[int] = None,
    checkpoint_every: Optional[int] = None,
    csv_path: Optional[str] = None
) -> pd.DataFrame:
    """
    Para cada linha com sof vazio: baixa o post e extrai todo o corpo.
    Respeita `limit` para testes (None = tudo).
    Salva checkpoints a cada N linhas se `checkpoint_every` for definido.
    """
    mask = (df["sof"].str.strip() == "")
    idxs = df[mask].index.tolist()
    if limit is not None:
        idxs = idxs[:limit]

    processed_since_ckpt = 0

    for i in tqdm(idxs, desc="Preenchendo SOF"):
        url = df.at[i, "url"].strip()
        if not url:
            continue
        try:
            html = fetch(url)
            if not html:
                continue

            # Atualiza title/canonical caso estejam vazios/desatualizados
            title, canon = extract_title_and_canonical(html, url)
            if title and (not df.at[i, "title"] or not df.at[i, "title"].strip()):
                df.at[i, "title"] = title
            if canon and canon != url:
                df.at[i, "url"] = canon

            sof_text = extract_sof(html)
            df.at[i, "sof"] = sof_text

            processed_since_ckpt += 1

            # checkpoint
            if checkpoint_every and csv_path and processed_since_ckpt >= checkpoint_every:
                df_ck = df.drop_duplicates(subset=["url"], keep="first")
                df_ck = df_ck.sort_values(by=["title"]).reset_index(drop=True)
                df_ck.to_csv(csv_path, index=False, quoting=csv.QUOTE_ALL, lineterminator="\n")
                processed_since_ckpt = 0

            # respeita o servidor
            time.sleep(0.2)

        except Exception as e:
            sys.stderr.write(f"[extract_sof] erro em {url}: {e}\n")

    return df


def main():
    ap = argparse.ArgumentParser(description="Preenche title/url e SOF do site BVS APS")
    ap.add_argument("--csv", default="sof.csv", help="caminho do CSV de entrada/saída (default: sof.csv)")
    ap.add_argument("--no-index", action="store_true", help="não varre o índice; só usa URLs já existentes no CSV")
    ap.add_argument("--only-index", action="store_true", help="apenas coleta o índice e salva; não preenche SOF")
    ap.add_argument("--pages", type=int, default=117, help="quantas páginas de índice varrer (default: 117)")
    ap.add_argument("--limit", type=int, default=None, help="limite de linhas sem SOF a preencher (debug)")
    ap.add_argument("--checkpoint-every", type=int, default=None, help="salva CSV a cada N SOFs preenchidas")
    args = ap.parse_args()

    df = ensure_csv(args.csv)

    if not args.no_index:
        posts = crawl_all_posts(max_pages=args.pages)
        df = merge_index_into_df(df, posts)

    if not args.only_index:
        df = fill_missing_sof(
            df,
            limit=args.limit,
            checkpoint_every=args.checkpoint_every,
            csv_path=args.csv,
        )

    # dedup, ordena por título
    df = df.drop_duplicates(subset=["url"], keep="first")
    df = df.sort_values(by=["title"]).reset_index(drop=True)

    # salva CSV com aspas em tudo (evita quebra de linha dentro de célula)
    df.to_csv(args.csv, index=False, quoting=csv.QUOTE_ALL, lineterminator="\n")
    print(f"✅ CSV salvo: {args.csv}  ({len(df)} linhas)")


if __name__ == "__main__":
    main()
