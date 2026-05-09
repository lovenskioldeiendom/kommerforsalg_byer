# Kommer-for-salg-monitor — Norges store byer

Daglig overvåkning av "Kommer for salg"-prosjekter på Finn.no for de syv største byene i Norge: Oslo, Bergen, Stavanger, Trondheim, Tromsø, Drammen, Kristiansand.

Sporer prosjekter som ennå ikke er i salgsstart — der utbyggere markedsfører før salgsoppgaven foreligger.

## Slik virker det

1. GitHub Actions kjører kl 06:53 norsk tid (med backup 09:53)
2. Scraperen henter Finn-søkeresultatene per kommune med `sub_form_type=planned`
3. For hvert prosjekt parses tidslinje, nøkkelinfo, beskrivelse
4. Snapshot lagres i `kommer-for-salg.db`
5. Endringer detekteres ved diff mot tidligere snapshot

## Forventet kjøretid

Avhenger av hvor mange prosjekter som er aktive — typisk 100-300 totalt på tvers av byene. Med 4 sekunders pause mellom requests gir det 10-25 minutter kjøretid.

Hvis kjøretiden nærmer seg 60-minutters grensen i GitHub Actions, kan vi redusere DELAY_BETWEEN_REQUESTS_S, eller dele kommunene i to parallelle workflows.

## Begrensninger

Samme som Akershus-versjonen — beskrivelser kan være kortfattede, "antall enheter" gjettes fra fritekst, og tidslinjefelt er fritekst ("Antatt 4. kvartal 2025").
