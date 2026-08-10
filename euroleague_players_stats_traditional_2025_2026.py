from __future__ import annotations

from pathlib import Path
import time

import pandas as pd
from selenium import webdriver
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait
from webdriver_manager.chrome import ChromeDriverManager

URL = (
    "https://www.euroleaguebasketball.net/en/euroleague/stats/players/"
    "?size=1000&viewType=traditional&statisticMode=perGame"
    "&seasonCode=E2025&seasonMode=Single&sortDirection=ascending&statistic="
)

COLUMNS = [
    "#", "Player", "Team", "GP", "GS", "Min", "PTS", "2PM", "2PA", "2P%",
    "3PM", "3PA", "3P%", "FTM", "FTA", "FT%", "OR", "DR", "TR", "AST",
    "STL", "TO", "BLK", "BLKA", "FC", "FD", "PIR",
]

OUTPUT_FILE = Path(
    "csv_files/csv_players_stats_files/"
    "euroleague_players_stats_traditional_2025_2026.csv"
)


def make_driver() -> webdriver.Chrome:
    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--window-size=1920,1080")
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--lang=en-US")

    return webdriver.Chrome(
        service=Service(ChromeDriverManager().install()),
        options=options,
    )


def accept_cookies(driver: webdriver.Chrome) -> None:
    """Bando priimti cookie langą, jeigu jis rodomas."""
    driver.execute_script(
        """
        const buttons = [...document.querySelectorAll('button')];
        const accept = buttons.find(button => /accept|allow all/i.test(button.innerText));
        if (accept) accept.click();
        """
    )


def extract_rows(driver: webdriver.Chrome) -> list[list[str]]:
    """Ištraukia lentelės/grid eilučių reikšmes, nenaudojant nestabilių CSS klasių."""
    return driver.execute_script(
        """
        const rowSelectors = ['table tbody tr', '[role="row"]'];
        const seen = new Set();
        const result = [];

        for (const selector of rowSelectors) {
          for (const row of document.querySelectorAll(selector)) {
            let cells = [...row.querySelectorAll(
              ':scope > td, :scope > [role="cell"], :scope > [role="gridcell"]'
            )];

            if (!cells.length) {
              cells = [...row.querySelectorAll(
                'td, [role="cell"], [role="gridcell"]'
              )];
            }

            const values = cells
              .map(cell => cell.innerText.replace(/\\s+/g, ' ').trim())
              .filter(Boolean);

            if (values.length < 10) continue;

            const key = values.join('|');
            if (!seen.has(key)) {
              seen.add(key);
              result.push(values);
            }
          }
        }

        return result;
        """
    )


def scrape_players() -> pd.DataFrame:
    driver = make_driver()

    try:
        driver.get(URL)
        accept_cookies(driver)

        wait = WebDriverWait(driver, 40)
        try:
            wait.until(lambda d: len(extract_rows(d)) > 1)
        except TimeoutException as exc:
            raise RuntimeError(
                "Nerasta statistikos lentelė. Pabandyk laikinai išjungti headless "
                "režimą ir patikrink, ar puslapis nerodo cookie arba bot-check lango."
            ) from exc

        time.sleep(2)
        raw_rows = extract_rows(driver)

        rows = [
            row[:len(COLUMNS)]
            for row in raw_rows
            if len(row) >= len(COLUMNS) and row[0].isdigit()
        ]

        if not rows:
            row_lengths = sorted({len(row) for row in raw_rows})
            raise RuntimeError(
                "Nerasta pilnų žaidėjų eilučių. "
                f"Rastų eilučių stulpelių skaičius: {row_lengths}"
            )

        df = pd.DataFrame(rows, columns=COLUMNS)
        df = df.drop_duplicates(subset=["#", "Player", "Team"])
        df = df.sort_values("#", key=lambda series: pd.to_numeric(series))
        df = df.reset_index(drop=True)

        OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
        df.to_csv(OUTPUT_FILE, index=False, encoding="utf-8-sig")
        return df
    finally:
        driver.quit()


def main() -> None:
    print("Scraping EuroLeague 2025-26 player traditional per-game stats...")
    df = scrape_players()
    print(f"Išsaugota žaidėjų: {len(df)}")
    print(f"CSV failas: {OUTPUT_FILE.resolve()}")
    print(df.head())


if __name__ == "__main__":
    main()