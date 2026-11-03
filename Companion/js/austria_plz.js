/**
 * austria_plz.js - Schnelle PLZ/Ort Zuordnung für Österreich
 * Zero-Dependency, offline-fähig und ultra-schnell auf leistungsschwachen Tablets.
 */

const AUSTRIAN_PLZ_DATABASE = {
  // Wien
  "1010": "Wien (Innere Stadt)",
  "1020": "Wien (Leopoldstadt)",
  "1030": "Wien (Landstraße)",
  "1040": "Wien (Wieden)",
  "1050": "Wien (Margareten)",
  "1060": "Wien (Mariahilf)",
  "1070": "Wien (Neubau)",
  "1080": "Wien (Josefstadt)",
  "1090": "Wien (Alsergrund)",
  "1100": "Wien (Favoriten)",
  "1110": "Wien (Simmering)",
  "1120": "Wien (Meidling)",
  "1130": "Wien (Hietzing)",
  "1140": "Wien (Penzing)",
  "1150": "Wien (Rudolfsheim-Fünfhaus)",
  "1160": "Wien (Ottakring)",
  "1170": "Wien (Hernals)",
  "1180": "Wien (Währing)",
  "1190": "Wien (Döbling)",
  "1200": "Wien (Brigittenau)",
  "1210": "Wien (Floridsdorf)",
  "1220": "Wien (Donaustadt)",
  "1230": "Wien (Liesing)",

  // Niederösterreich
  "2000": "Stockerau",
  "2100": "Korneuburg",
  "2130": "Mistelbach",
  "2230": "Gänserndorf",
  "2320": "Schwechat",
  "2340": "Mödling",
  "2345": "Brunn am Gebirge",
  "2351": "Wiener Neudorf",
  "2353": "Guntramsdorf",
  "2380": "Perchtoldsdorf",
  "2460": "Bruck an der Leitha",
  "2500": "Baden",
  "2514": "Traiskirchen",
  "2540": "Bad Vöslau",
  "2620": "Neunkirchen",
  "2700": "Wiener Neustadt",
  "3100": "St. Pölten",
  "3130": "Herzogenburg",
  "3250": "Wieselburg",
  "3300": "Amstetten",
  "3340": "Waidhofen an der Ybbs",
  "3400": "Klosterneuburg",
  "3430": "Tulln an der Donau",
  "3500": "Krems an der Donau",
  "3580": "Horn",
  "3830": "Waidhofen an der Thaya",
  "3910": "Zwettl",

  // Oberösterreich
  "4020": "Linz",
  "4030": "Linz",
  "4040": "Linz",
  "4050": "Traun",
  "4060": "Leonding",
  "4070": "Eferding",
  "4150": "Rohrbach-Berg",
  "4210": "Gallneukirchen",
  "4240": "Freistadt",
  "4300": "St. Valentin",
  "4320": "Perg",
  "4400": "Steyr",
  "4470": "Enns",
  "4540": "Bad Hall",
  "4560": "Kirchdorf an der Krems",
  "4600": "Wels",
  "4690": "Schwanenstadt",
  "4710": "Grieskirchen",
  "4780": "Schärding",
  "4810": "Gmunden",
  "4820": "Bad Ischl",
  "4840": "Vöcklabruck",
  "4910": "Ried im Innkreis",

  // Salzburg
  "5020": "Salzburg",
  "5023": "Salzburg",
  "5026": "Salzburg",
  "5071": "Wals-Siezenheim",
  "5110": "Oberndorf bei Salzburg",
  "5201": "Seekirchen am Wallersee",
  "5300": "Hallwang",
  "5400": "Hallein",
  "5500": "Bischofshofen",
  "5600": "St. Johann im Pongau",
  "5700": "Zell am See",
  "5730": "Mittersill",

  // Tirol
  "6020": "Innsbruck",
  "6060": "Hall in Tirol",
  "6112": "Wattens",
  "6130": "Schwaz",
  "6170": "Zirl",
  "6176": "Völs",
  "6200": "Jenbach",
  "6300": "Wörgl",
  "6330": "Kufstein",
  "6370": "Kitzbühel",
  "6410": "Telfs",
  "6460": "Imst",
  "6500": "Landeck",
  "6600": "Reutte",
  "9900": "Lienz",

  // Vorarlberg
  "6800": "Feldkirch",
  "6830": "Rankweil",
  "6845": "Hohenems",
  "6850": "Dornbirn",
  "6890": "Lustenau",
  "6900": "Bregenz",
  "6971": "Hard",

  // Burgenland
  "7000": "Eisenstadt",
  "7011": "Siegendorf",
  "7052": "Müllendorf",
  "7100": "Neusiedl am See",
  "7210": "Mattersburg",
  "7350": "Oberpullendorf",
  "7400": "Oberwart",
  "7540": "Güssing",
  "7571": "Rudersdorf",
  "7580": "Jennersdorf",

  // Steiermark
  "8010": "Graz",
  "8020": "Graz",
  "8041": "Graz",
  "8051": "Graz",
  "8054": "Graz",
  "8055": "Graz",
  "8073": "Feldkirchen bei Graz",
  "8074": "Raaba-Grambach",
  "8101": "Gratkorn",
  "8160": "Weiz",
  "8200": "Gleisdorf",
  "8230": "Hartberg",
  "8280": "Fürstenfeld",
  "8330": "Feldbach",
  "8430": "Leibnitz",
  "8530": "Deutschlandsberg",
  "8570": "Voitsberg",
  "8600": "Bruck an der Mur",
  "8605": "Kapfenberg",
  "8700": "Leoben",
  "8720": "Knittelfeld",
  "8740": "Zeltweg",
  "8750": "Judenburg",
  "8850": "Murau",
  "8940": "Liezen",
  "8970": "Schladming",

  // Kärnten
  "9020": "Klagenfurt am Wörthersee",
  "9100": "Völkermarkt",
  "9170": "Ferlach",
  "9220": "Velden am Wörther See",
  "9300": "St. Veit an der Glan",
  "9400": "Wolfsberg",
  "9462": "Bad St. Leonhard",
  "9500": "Villach",
  "9560": "Feldkirchen in Kärnten",
  "9620": "Hermagor",
  "9800": "Spittal an der Drau"
};

/**
 * Sucht nach einem Ort zur angegebenen PLZ.
 * Falls die PLZ 4-stellig ist und gefunden wird, wird der Ort zurückgegeben.
 */
function lookupAustrianCity(plz) {
  if (!plz) return null;
  const cleanPlz = String(plz).trim();
  return AUSTRIAN_PLZ_DATABASE[cleanPlz] || null;
}

// Standardmäßige Schnell-Auswahl für die Praxis
const DEFAULT_QUICK_CITIES = [
  { plz: "1010", ort: "Wien" },
  { plz: "1020", ort: "Wien" },
  { plz: "1030", ort: "Wien" },
  { plz: "2340", ort: "Mödling" },
  { plz: "2500", ort: "Baden" },
  { plz: "2700", ort: "Wr. Neustadt" },
  { plz: "3100", ort: "St. Pölten" },
  { plz: "4020", ort: "Linz" },
  { plz: "5020", ort: "Salzburg" },
  { plz: "8010", ort: "Graz" }
];

