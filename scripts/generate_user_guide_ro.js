/**
 * Generator pentru ghidul utilizatorului în limba română.
 *
 * Generează `docs/user-guide/Ghid_Utilizator_Fogli_di_Percorso_RO.docx`
 * cu acoperire copertă, cuprins, secțiuni cu placeholder-uri pentru
 * capturile de ecran și subsol cu numerotare pagini.
 *
 * SETUP (o singură dată):
 *   npm install                  # instalează pachetul `docx` (din package.json)
 *
 * RULARE:
 *   node scripts/generate_user_guide_ro.js
 *   # sau echivalent:
 *   npm run build-guide-ro
 */
const fs = require("fs");
const path = require("path");
const {
    Document, Packer, Paragraph, TextRun, Table, TableRow, TableCell,
    Header, Footer, AlignmentType, PageOrientation, LevelFormat,
    TabStopType, TabStopPosition, TableOfContents, HeadingLevel,
    BorderStyle, WidthType, ShadingType, PageNumber, PageBreak,
    ImageRun,
} = require("docx");

const OUTPUT = path.resolve(__dirname, "..", "docs", "user-guide",
    "Ghid_Utilizator_Fogli_di_Percorso_RO.docx");

const CAPTURES_DIR = path.resolve(__dirname, "..", "docs", "user-guide", "capturi");

// US Letter portrait — comod pentru tipărire
const PAGE = {
    width: 12240,
    height: 15840,
    margins: { top: 1440, right: 1440, bottom: 1440, left: 1440 },
};
const CONTENT_WIDTH = PAGE.width - PAGE.margins.left - PAGE.margins.right; // 9360

// ---------- helpers ----------

function p(text, opts = {}) {
    return new Paragraph({
        children: [new TextRun({ text, ...opts.run })],
        ...opts.para,
    });
}

function heading(text, level) {
    return new Paragraph({
        heading: level,
        children: [new TextRun({ text })],
    });
}

function bullet(text) {
    return new Paragraph({
        numbering: { reference: "bullets", level: 0 },
        children: [new TextRun({ text })],
    });
}

function numbered(text) {
    return new Paragraph({
        numbering: { reference: "numbers", level: 0 },
        children: [new TextRun({ text })],
    });
}

/** Inserează o captură reală dintr-un fișier PNG, dacă există. Altfel cade pe placeholder. */
function screenshotImage(filename, caption) {
    const filePath = path.join(CAPTURES_DIR, filename);
    if (!fs.existsSync(filePath)) {
        console.warn(`  ! PNG missing: ${filename} -> using placeholder`);
        return screenshotPlaceholder(caption, [`File aşteptat: capturi/${filename}`]);
    }
    // Capturile sunt 1440x900. Le scalăm la lăţimea conţinutului (9360 DXA ≈ 6.5 inch ≈ 624 px @96DPI).
    const w = 624;
    const h = Math.round(w * (900 / 1440)); // 390
    return [
        new Paragraph({
            alignment: AlignmentType.CENTER,
            children: [new ImageRun({
                type: "png",
                data: fs.readFileSync(filePath),
                transformation: { width: w, height: h },
                altText: { title: caption, description: caption, name: filename },
            })],
        }),
        new Paragraph({
            alignment: AlignmentType.CENTER,
            children: [new TextRun({
                text: caption,
                italics: true, size: 18, color: "555555",
            })],
        }),
    ];
}

/** Placeholder pentru captură de ecran: tabel cu o singură celulă, fundal gri, text descriptiv. */
function screenshotPlaceholder(caption, hintLines) {
    const border = { style: BorderStyle.DASHED, size: 6, color: "888888" };
    const borders = { top: border, bottom: border, left: border, right: border };
    const lines = [
        new Paragraph({
            alignment: AlignmentType.CENTER,
            children: [new TextRun({
                text: "📷  CAPTURĂ DE ECRAN",
                bold: true, size: 22, color: "555555",
            })],
        }),
        new Paragraph({
            alignment: AlignmentType.CENTER,
            children: [new TextRun({ text: caption, italics: true, size: 20, color: "555555" })],
        }),
    ];
    for (const h of hintLines) {
        lines.push(new Paragraph({
            alignment: AlignmentType.CENTER,
            children: [new TextRun({ text: h, size: 18, color: "777777" })],
        }));
    }
    // adăugăm padding vertical
    lines.unshift(new Paragraph({ children: [new TextRun(" ")] }));
    lines.push(new Paragraph({ children: [new TextRun(" ")] }));

    return new Table({
        width: { size: CONTENT_WIDTH, type: WidthType.DXA },
        columnWidths: [CONTENT_WIDTH],
        rows: [new TableRow({
            children: [new TableCell({
                borders,
                width: { size: CONTENT_WIDTH, type: WidthType.DXA },
                shading: { fill: "F2F2F2", type: ShadingType.CLEAR },
                margins: { top: 200, bottom: 200, left: 200, right: 200 },
                children: lines,
            })],
        })],
    });
}

/** Casetă „info / atenție / sfat". */
function callout(kind, title, body) {
    const colors = {
        info: { bg: "DBE9F4", border: "2E75B6", icon: "ℹ️" },
        warn: { bg: "FFF3CD", border: "B58A00", icon: "⚠️" },
        tip:  { bg: "D9EAD3", border: "38761D", icon: "💡" },
    }[kind] || { bg: "EEEEEE", border: "888888", icon: "•" };
    const border = { style: BorderStyle.SINGLE, size: 8, color: colors.border };
    const borders = { top: border, bottom: border, left: border, right: border };
    return new Table({
        width: { size: CONTENT_WIDTH, type: WidthType.DXA },
        columnWidths: [CONTENT_WIDTH],
        rows: [new TableRow({
            children: [new TableCell({
                borders,
                width: { size: CONTENT_WIDTH, type: WidthType.DXA },
                shading: { fill: colors.bg, type: ShadingType.CLEAR },
                margins: { top: 120, bottom: 120, left: 200, right: 200 },
                children: [
                    new Paragraph({
                        children: [new TextRun({
                            text: `${colors.icon}  ${title}`,
                            bold: true, color: colors.border,
                        })],
                    }),
                    new Paragraph({ children: [new TextRun({ text: body })] }),
                ],
            })],
        })],
    });
}

function tableSimple(headers, rows) {
    const colW = Math.floor(CONTENT_WIDTH / headers.length);
    const columnWidths = headers.map(() => colW);
    columnWidths[columnWidths.length - 1] = CONTENT_WIDTH - colW * (headers.length - 1);
    const border = { style: BorderStyle.SINGLE, size: 1, color: "BBBBBB" };
    const borders = { top: border, bottom: border, left: border, right: border };
    const headerRow = new TableRow({
        children: headers.map((h, i) => new TableCell({
            borders,
            width: { size: columnWidths[i], type: WidthType.DXA },
            shading: { fill: "0B2A5B", type: ShadingType.CLEAR },
            margins: { top: 80, bottom: 80, left: 120, right: 120 },
            children: [new Paragraph({
                children: [new TextRun({ text: h, bold: true, color: "FFFFFF" })],
            })],
        })),
    });
    const dataRows = rows.map((r, ri) => new TableRow({
        children: r.map((c, i) => new TableCell({
            borders,
            width: { size: columnWidths[i], type: WidthType.DXA },
            shading: ri % 2 === 1 ? { fill: "F7F7F7", type: ShadingType.CLEAR } : undefined,
            margins: { top: 80, bottom: 80, left: 120, right: 120 },
            children: [new Paragraph({ children: [new TextRun({ text: c })] })],
        })),
    }));
    return new Table({
        width: { size: CONTENT_WIDTH, type: WidthType.DXA },
        columnWidths,
        rows: [headerRow, ...dataRows],
    });
}

const PB = () => new Paragraph({ children: [new PageBreak()] });

// ---------- conținut ----------

const cover = [
    new Paragraph({
        alignment: AlignmentType.CENTER,
        spacing: { before: 2400, after: 240 },
        children: [new TextRun({ text: "Fogli di Percorso", bold: true, size: 64, color: "0B2A5B" })],
    }),
    new Paragraph({
        alignment: AlignmentType.CENTER,
        spacing: { before: 0, after: 1200 },
        children: [new TextRun({ text: "Ghid de utilizare", size: 36, color: "555555" })],
    }),
    new Paragraph({
        alignment: AlignmentType.CENTER,
        children: [new TextRun({
            text: "Aplicație pentru gestiunea rambursărilor de transport (carburant și taxi)",
            italics: true, size: 24, color: "777777",
        })],
    }),
    new Paragraph({
        alignment: AlignmentType.CENTER,
        spacing: { before: 240, after: 240 },
        children: [new TextRun({ text: "Limba: română", size: 22, color: "777777" })],
    }),
    new Paragraph({
        alignment: AlignmentType.CENTER,
        spacing: { before: 3600 },
        children: [new TextRun({ text: "VANDEWIELE Romania", bold: true, size: 28 })],
    }),
    new Paragraph({
        alignment: AlignmentType.CENTER,
        children: [new TextRun({ text: "Versiunea 1.0  •  Mai 2026", size: 20, color: "777777" })],
    }),
    PB(),
];

const tocSection = [
    heading("Cuprins", HeadingLevel.HEADING_1),
    new TableOfContents("Cuprins", { hyperlink: true, headingStyleRange: "1-2" }),
    PB(),
];

const sec1 = [
    heading("1. Introducere", HeadingLevel.HEADING_1),
    p("Bine ai venit în aplicația Fogli di Percorso! Acest sistem îți permite să declari deplasările pe care le-ai efectuat în interes de serviciu și să primești rambursarea aferentă (combustibil sau taxi)."),
    p(" "),
    heading("1.1 La ce servește aplicația", HeadingLevel.HEADING_2),
    bullet("Salvezi o singură dată punctul tău de plecare obișnuit pe hartă."),
    bullet("La sfârșitul fiecărei luni, declari numărul de călătorii dus-întors efectuate și încarci foaia de traseu (PDF)."),
    bullet("Pentru rambursările de tip taxi, încarci de asemenea chitanțele scanate."),
    bullet("Sistemul calculează automat suma de rambursat în EUR și RON (folosind cursul BNR)."),
    bullet("După trimitere, declarația rămâne arhivată și poate fi consultată oricând."),
    p(" "),
    heading("1.2 Cine poate folosi aplicația", HeadingLevel.HEADING_2),
    p("Toți angajații VANDEWIELE Romania care au cont activ în sistemul HR. Există două roluri:"),
    bullet("Utilizator normal: poate să declare propriile deplasări."),
    bullet("Administrator (FunctionCode ≥ 60): în plus, poate să introducă declarații în numele colegilor din același SubCdc, să consulte istoricul tuturor declarațiilor, să exporte rapoartele Excel și să administreze cursurile BNR și tarifele per kilometru."),
    p(" "),
    callout("info", "Acces", "Aplicația este accesibilă de la adresa: http://192.168.10.72:5010 (rețea internă). Te poți conecta cu același nume de utilizator și parolă pe care le folosești în alte aplicații interne."),
    PB(),
];

const sec2 = [
    heading("2. Autentificare", HeadingLevel.HEADING_1),
    p("Pentru a accesa orice funcție a aplicației, trebuie mai întâi să te autentifici."),
    p(" "),
    heading("Pași", HeadingLevel.HEADING_2),
    numbered("Deschide browserul (Chrome, Edge sau Firefox) și mergi la adresa http://192.168.10.72:5010"),
    numbered("Vei fi redirecționat automat către pagina de Autentificare."),
    numbered("Introdu numele de utilizator (nume de cont HR, ex. nume.prenume) în câmpul „Utilizator”."),
    numbered("Introdu parola în câmpul „Parolă”."),
    numbered("Apasă butonul „Intră”."),
    p(" "),
    ...screenshotImage("01-login.png", "Pagina de autentificare (limba RO)"),
    p(" "),
    callout("warn", "Atenție", "După 5 încercări greșite consecutive, contul este blocat pentru 15 minute. Așteaptă acest interval sau contactează administratorul."),
    p(" "),
    callout("tip", "Schimbarea limbii înainte de autentificare",
        "Pe partea dreaptă-sus a paginii sunt 3 butoane: RO IT EN. Apasă pe unul dintre ele pentru a schimba imediat limba interfeței. Limba aleasă rămâne memorată într-un cookie pentru un an."),
    PB(),
];

const sec3 = [
    heading("3. Pagina principală (Acasă)", HeadingLevel.HEADING_1),
    p("După autentificare ești dus pe pagina principală, care îți arată cele mai importante acțiuni disponibile."),
    p(" "),
    ...screenshotImage("02-dashboard.png", "Pagina principală (dashboard) cu cele 3 carduri"),
    p(" "),
    heading("3.1 Cardul „Punct de plecare”", HeadingLevel.HEADING_2),
    p("Aici definești sau actualizezi adresa de la care pleci de obicei spre sediu. Aplicația folosește acest punct ca referință pentru a calcula distanța one-way."),
    p(" "),
    heading("3.2 Cardul „Declarații”", HeadingLevel.HEADING_2),
    p("Aici introduci declarațiile lunare, încarci documente PDF și consulți declarațiile tale anterioare."),
    p(" "),
    heading("3.3 Cardul „Administrare” (doar admin)", HeadingLevel.HEADING_2),
    p("Vizibil doar dacă ai FunctionCode ≥ 60. Permite reprezentarea colegilor și administrarea ratelor de schimb și a tarifelor."),
    PB(),
];

const sec4 = [
    heading("4. Definirea punctului de plecare", HeadingLevel.HEADING_1),
    p("Înainte de a introduce prima declarație, trebuie să spui sistemului unde se află punctul tău obișnuit de plecare. Acest pas se face o singură dată."),
    p(" "),
    heading("Pași", HeadingLevel.HEADING_2),
    numbered("Din pagina principală apasă cardul „Punct de plecare” → buton „Mergi la hartă”."),
    numbered("Apare o hartă interactivă centrată pe Romania."),
    numbered("Fă clic pe locul exact unde se află adresa ta (poți face zoom cu rotița mouse-ului)."),
    numbered("Apare un marker cu coordonatele și o casetă de text „Etichetă”."),
    numbered("Completează eticheta (ex. „Casă”, „Strada Mihai Eminescu 5”)."),
    numbered("Apasă „Salvează punctul de plecare”."),
    p(" "),
    ...screenshotImage("03-punct-de-plecare.png", "Hartă pentru selectarea punctului de plecare"),
    p(" "),
    callout("info", "Modificarea punctului",
        "Poți să ai un singur punct activ. Pentru a-l schimba, mai întâi șterge-l (buton „Cancellare” pe pagina actuală), apoi alege locul nou pe hartă."),
    PB(),
];

const sec5 = [
    heading("5. Crearea unei declarații lunare", HeadingLevel.HEADING_1),
    p("Declarațiile se referă la o lună calendaristică completă (ex. „Aprilie 2026”). Poți să le salvezi ca ciornă oricând, dar trimiterea definitivă este permisă doar între ziua 1 și ziua 5 a lunii următoare."),
    p(" "),
    heading("5.1 Pașii pentru o nouă declarație", HeadingLevel.HEADING_2),
    numbered("Din pagina principală apasă „Declarații” → „Mergi la declarații”."),
    numbered("Apasă „Nouă declarație”."),
    numbered("Alege luna și anul pentru care faci declarația."),
    numbered("Alege „Tipul rambursării”: Combustibil sau Taxi."),
    numbered("Introdu „Număr călătorii dus-întors” (un drum dus-întors = 1 călătorie)."),
    numbered("Dacă tipul este Taxi, adaugă pentru fiecare chitanță valoarea în EUR."),
    numbered("Încarcă PDF-ul cu foaia de traseu (max 5 MB)."),
    numbered("Pentru Taxi, încarcă și chitanțele scanate (PDF, max 5 MB fiecare)."),
    numbered("Verifică previzualizarea sumei rambursate."),
    numbered("Apasă „Salvează ciorna” pentru a păstra fără a trimite, sau „Salvează și trimite” pentru trimiterea definitivă."),
    p(" "),
    ...screenshotImage("05-noua-declaratie.png", "Formular declarație nouă"),
    p(" "),
    heading("5.2 Diferența între „Ciornă” și „Trimisă”", HeadingLevel.HEADING_2),
    tableSimple(
        ["Stare", "Caracteristici"],
        [
            ["CIORNĂ (DRAFT)", "Poate fi modificată sau ștearsă oricând până la trimiterea definitivă. Nu primește număr de registru."],
            ["TRIMISĂ (SUBMITTED)", "Are număr de registru atribuit (ex. RegistryId 1234). Nu mai poate fi modificată. Apare în raportul lunar Excel."],
        ]
    ),
    p(" "),
    callout("warn", "Perioada de trimitere",
        "Trimiterea definitivă este permisă doar între ziua 1 și ziua 5 a lunii următoare lunii declarate. În afara acestui interval, butonul „Salvează și trimite” este dezactivat. Salvarea ca ciornă este permisă oricând."),
    p(" "),
    heading("5.3 Vizualizarea declarațiilor mele", HeadingLevel.HEADING_2),
    p("Apasă „Declarații” → „Mergi la declarații”. Apare lista cu toate declarațiile tale, ordonate de la cea mai recentă."),
    bullet("Apasă pe „Detalii” pentru a vedea/edita o ciornă, sau pentru a consulta o declarație trimisă."),
    bullet("Pentru ciorne, butonul „Modifică ciorna” deschide formularul de editare."),
    bullet("Pentru declarații trimise, vezi sumarul și PDF-urile încărcate (descărcabile)."),
    p(" "),
    ...screenshotImage("04-lista-declaratii.png", "Lista declarațiilor mele"),
    PB(),
];

const sec6 = [
    heading("6. Schimbarea limbii", HeadingLevel.HEADING_1),
    p("Aplicația este disponibilă în 3 limbi: română (RO), italiană (IT) și engleză (EN)."),
    p(" "),
    heading("Pași", HeadingLevel.HEADING_2),
    numbered("În colțul din dreapta-sus al oricărei pagini sunt 3 butoane mici cu codurile limbilor."),
    numbered("Apasă pe limba dorită."),
    numbered("Pagina se reîncarcă imediat în limba aleasă."),
    numbered("Alegerea este memorată într-un cookie și se păstrează la următoarele vizite."),
    p(" "),
    ...screenshotImage("02-dashboard.png", "Selectorul de limbă: vedeți „Limba: RO IT EN” în colțul din dreapta-sus al barei de navigare"),
    p(" "),
    callout("info", "Limba implicită",
        "Pentru utilizatorii noi care nu au ales încă o limbă, sistemul folosește română ca limbă implicită."),
    PB(),
];

const sec7 = [
    heading("7. Funcții pentru administratori", HeadingLevel.HEADING_1),
    p("Această secțiune este vizibilă doar pentru utilizatorii cu FunctionCode ≥ 60. Conținutul cardului „Administrare” deschide o zonă dedicată din care poți:"),
    bullet("Vezi colegii pe care îi poți reprezenta."),
    bullet("Introduci declarații în numele colegilor."),
    bullet("Consulți istoricul tuturor declarațiilor din SubCdc-ul tău."),
    bullet("Exporți raportul lunar în format Excel."),
    bullet("Administrezi cursurile BNR EUR-RON."),
    bullet("Administrezi tarifele per kilometru (consum + preț combustibil)."),
    p(" "),
    heading("7.1 Reprezentarea colegilor", HeadingLevel.HEADING_2),
    p("Din pagina „Administrare” → „Mergi la zona admin” vezi tabelul cu colegii pe care ai dreptul să-i reprezinți (același SubCdc, FunctionCode mai mic decât al tău)."),
    bullet("Buton „Harta”: ajungi pe pagina de hartă cu posibilitatea să modifici punctul de plecare al colegului."),
    bullet("Buton „Declarație nouă”: ajungi pe formularul de declarație, dar declarația va fi atribuită colegului (nu ție)."),
    p(" "),
    ...screenshotImage("06-admin-representable.png", "Lista colegilor reprezentabili"),
    p(" "),
    heading("7.2 Istoricul declarațiilor SubCdc", HeadingLevel.HEADING_2),
    p("Din zona admin, link „Istoric declarații SubCdc” → vezi toate declarațiile (ciornele și trimise) ale tuturor colegilor din SubCdc-ul tău."),
    bullet("Poți filtra după an, lună și tip de rambursare."),
    bullet("Apasă pe „Detalii” lângă o linie pentru a vedea declarația completă."),
    p(" "),
    callout("warn", "Limită de 500 de rânduri",
        "Pentru a evita încărcarea excesivă a paginii, sistemul afișează maximum 500 de rânduri. Dacă vezi un mesaj de avertizare „Rezultate trunchiate la 500 de rânduri”, restrânge filtrele (an, lună, tip) pentru a vedea datele complete. Aceeași limită se aplică și la exportul Excel."),
    p(" "),
    ...screenshotImage("07b-admin-istoric-filtrat.png", "Pagina de istoric cu filtre și tabel (an + lună selectate)"),
    p(" "),
    heading("7.3 Exportul Excel", HeadingLevel.HEADING_2),
    p("Pe pagina de istoric, atunci când ai filtrat după anul și luna dorite, apare butonul „Export XLSX”."),
    bullet("Apasă butonul → browserul descarcă un fișier cu numele fogli-di-percorso-AAAA-LL.xlsx."),
    bullet("Dacă lista a fost trunchiată la 500 de rânduri, numele fișierului devine fogli-di-percorso-AAAA-LL-truncated.xlsx și pe prima linie din sheet apare un avertisment galben."),
    bullet("Fișierul conține toate declarațiile lunii cu: angajat, tip, stare, număr de călătorii, kilometri, sumă în EUR, număr de registru, data trimiterii."),
    p(" "),
    heading("7.4 Administrarea cursurilor BNR EUR-RON", HeadingLevel.HEADING_2),
    p("Sistemul folosește cursul BNR pentru a converti suma EUR în RON. Există două surse:"),
    bullet("Cursuri STANDARD: introdusese manual de administrator, cu o valoare validă într-un interval (ex. valid de la 1 ianuarie 2026 până la 31 martie 2026)."),
    bullet("Cursuri LIVE: dacă nu există un curs standard pentru data declarației, sistemul preia automat cursul de la BNR.ro sau cursbnr.ro la momentul trimiterii."),
    p(" "),
    heading("Adăugarea unui curs standard nou", HeadingLevel.HEADING_3),
    numbered("Mergi la „Administrare” → „Gestionează cursuri BNR EUR-RON”."),
    numbered("În secțiunea „Adaugă curs standard nou” introdu valoarea (ex. 4.9756)."),
    numbered("Alege data „Valabil de la” și opțional data „Valabil până la”."),
    numbered("Apasă „Salvează cursul”."),
    p(" "),
    ...screenshotImage("08-admin-bnr.png", "Pagina cursurilor BNR EUR-RON"),
    p(" "),
    heading("7.5 Administrarea tarifelor €/km", HeadingLevel.HEADING_2),
    p("Tariful per kilometru este calculat ca prețul combustibilului împărțit la consumul mediu. Administratorul actualizează aceste două valori atunci când prețul combustibilului se schimbă semnificativ."),
    p(" "),
    heading("Adăugarea unei tarife noi", HeadingLevel.HEADING_3),
    numbered("Mergi la „Administrare” → „Gestionează tarifele €/km”."),
    numbered("Introdu „Consum mediu (km/L)” (ex. 15.00)."),
    numbered("Introdu „Preț mediu combustibil (EUR/L)” (ex. 1.700)."),
    numbered("Alege „Valabil de la” și opțional „Valabil până la”."),
    numbered("Apasă „Salvează tariful”."),
    p(" "),
    ...screenshotImage("09-admin-fuel-rates.png", "Pagina tarifelor €/km"),
    p(" "),
    callout("info", "Versionarea tarifelor",
        "Fiecare tarif nou creează o versiune nouă. Declarațiile deja trimise rămân „înghețate” pe RateId-ul folosit la momentul trimiterii — nu sunt recalculate atunci când introduci o tarifă nouă."),
    PB(),
];

const sec8 = [
    heading("8. Întrebări frecvente", HeadingLevel.HEADING_1),
    p(" "),
    heading("Am uitat să trimit declarația până în ziua 5. Ce fac?", HeadingLevel.HEADING_3),
    p("Salveaz-o ca ciornă oricând și contactează un administrator (utilizator cu FunctionCode ≥ 70). Administratorul poate trimite declarația în numele tău chiar și după depășirea termenului (există un buton special „Trimite (override admin)” pentru aceste cazuri)."),
    p(" "),
    heading("Pot să corectez o declarație după ce am trimis-o?", HeadingLevel.HEADING_3),
    p("Nu. Declarațiile trimise sunt înghețate pentru audit. Contactează administratorul care poate șterge declarația greșită (numai dacă a fost trimisă „din eroare”) și poate să o reintroducă corect."),
    p(" "),
    heading("De ce nu văd cardul „Administrare” pe pagina principală?", HeadingLevel.HEADING_3),
    p("Cardul este vizibil doar pentru utilizatorii cu FunctionCode ≥ 60. Dacă nu îl vezi, înseamnă că nu ai acest rol."),
    p(" "),
    heading("De ce mi se afișează „A active declaration already exists for this month”?", HeadingLevel.HEADING_3),
    p("Există deja o declarație (ciornă sau trimisă) pentru luna respectivă. Mergi la „Declarații mele” și deschide-o pentru a o modifica, sau șterge ciorna existentă dacă vrei să o iei de la zero."),
    p(" "),
    heading("Suma în RON apare goală pe declarația mea. De ce?", HeadingLevel.HEADING_3),
    p("Aplicația încearcă să preia cursul BNR la momentul trimiterii. Dacă sursa externă (BNR.ro / cursbnr.ro) nu este disponibilă și nu există un curs STANDARD configurat de admin, sistemul salvează declarația cu RON necompletat. Coloana RON poate fi recalculată ulterior."),
    p(" "),
    heading("Cum schimb adresa de plecare?", HeadingLevel.HEADING_3),
    p("Mergi la „Punct de plecare” → buton „Cancellare” pentru a șterge punctul existent, apoi click pe noua locație pe hartă și salvează."),
    p(" "),
    heading("Pot să fac declarația de pe telefon?", HeadingLevel.HEADING_3),
    p("Da, aplicația folosește un layout responsive Bootstrap. Funcționează pe smartphone-uri și tablete, însă încărcarea PDF-urilor este mai comodă de pe un calculator unde scanerul/fișierele sunt deja salvate."),
    p(" "),
    heading("Cum contactez suportul?", HeadingLevel.HEADING_3),
    p("Trimite un email la echipa IT internă, cu screenshot al ecranului (F12 → Network dacă este o problemă tehnică) și descrierea pașilor făcuți înainte de eroare."),
    PB(),
];

const sec9 = [
    heading("9. Glosar", HeadingLevel.HEADING_1),
    tableSimple(
        ["Termen", "Definiție"],
        [
            ["Fogli di Percorso", "Numele aplicației (italiană: „foi de traseu”)."],
            ["SubCdc", "Subdiviziune a unui centru de cost. Grupare organizațională pentru cine raportează aceluiași responsabil."],
            ["FunctionCode (FC)", "Cod numeric care indică nivelul ierarhic / funcția în firmă. FC ≥ 60 = acces admin."],
            ["Curs BNR", "Cursul oficial de schimb EUR/RON publicat de Banca Națională a României."],
            ["RateId", "Identificator al unei tarife €/km. Fiecare declarație îngheață RateId-ul la momentul trimiterii."],
            ["RegistryId", "Numărul oficial de registru atribuit de sistem la trimiterea unei declarații. Apare pe export Excel și pe pagina de detalii."],
            ["Foaie traseu", "PDF cu detalii kilometraj / itinerar, încărcat obligatoriu pentru fiecare declarație."],
        ]
    ),
];

// ---------- asamblare ----------

const doc = new Document({
    creator: "Generator automat",
    title: "Ghid utilizator Fogli di Percorso",
    description: "Manual de utilizare pentru aplicația de rambursări transport.",
    styles: {
        default: { document: { run: { font: "Arial", size: 22 } } },
        paragraphStyles: [
            {
                id: "Heading1", name: "Heading 1", basedOn: "Normal", next: "Normal", quickFormat: true,
                run: { size: 36, bold: true, font: "Arial", color: "0B2A5B" },
                paragraph: { spacing: { before: 360, after: 240 }, outlineLevel: 0 },
            },
            {
                id: "Heading2", name: "Heading 2", basedOn: "Normal", next: "Normal", quickFormat: true,
                run: { size: 28, bold: true, font: "Arial", color: "2E75B6" },
                paragraph: { spacing: { before: 240, after: 180 }, outlineLevel: 1 },
            },
            {
                id: "Heading3", name: "Heading 3", basedOn: "Normal", next: "Normal", quickFormat: true,
                run: { size: 24, bold: true, font: "Arial", color: "555555" },
                paragraph: { spacing: { before: 180, after: 120 }, outlineLevel: 2 },
            },
        ],
    },
    numbering: {
        config: [
            {
                reference: "bullets",
                levels: [{
                    level: 0, format: LevelFormat.BULLET, text: "•",
                    alignment: AlignmentType.LEFT,
                    style: { paragraph: { indent: { left: 720, hanging: 360 } } },
                }],
            },
            {
                reference: "numbers",
                levels: [{
                    level: 0, format: LevelFormat.DECIMAL, text: "%1.",
                    alignment: AlignmentType.LEFT,
                    style: { paragraph: { indent: { left: 720, hanging: 360 } } },
                }],
            },
        ],
    },
    sections: [{
        properties: {
            page: { size: { width: PAGE.width, height: PAGE.height }, margin: PAGE.margins },
        },
        headers: {
            default: new Header({
                children: [new Paragraph({
                    alignment: AlignmentType.RIGHT,
                    children: [new TextRun({
                        text: "Fogli di Percorso — Ghid utilizator", color: "999999", size: 18,
                    })],
                })],
            }),
        },
        footers: {
            default: new Footer({
                children: [new Paragraph({
                    alignment: AlignmentType.CENTER,
                    children: [
                        new TextRun({ text: "Pagina ", color: "999999", size: 18 }),
                        new TextRun({ children: [PageNumber.CURRENT], color: "999999", size: 18 }),
                        new TextRun({ text: " din ", color: "999999", size: 18 }),
                        new TextRun({ children: [PageNumber.TOTAL_PAGES], color: "999999", size: 18 }),
                    ],
                })],
            }),
        },
        children: [
            ...cover,
            ...tocSection,
            ...sec1,
            ...sec2,
            ...sec3,
            ...sec4,
            ...sec5,
            ...sec6,
            ...sec7,
            ...sec8,
            ...sec9,
        ],
    }],
});

Packer.toBuffer(doc).then((buffer) => {
    fs.writeFileSync(OUTPUT, buffer);
    console.log(`Wrote ${OUTPUT} (${buffer.length} bytes)`);
}).catch((err) => {
    console.error("ERROR generating docx:", err);
    process.exit(1);
});
