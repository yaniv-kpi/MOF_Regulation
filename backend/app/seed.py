"""
Seed script — loads sample Israeli regulation documents for local development.
Run with:  python -m app.seed

This lets you test the search UI without waiting for a full crawl.
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from app.database import engine, SessionLocal
from app.models import Base, Document
from sqlalchemy import text

SAMPLE_DOCS = [
    {
        "title": "תקנות הגנת הצרכן (ביטול עסקה), התשע\"א-2010",
        "content": (
            "תקנות אלה קובעות את זכויות הצרכן לביטול עסקה שנעשתה מרחוק או מחוץ לעסק. "
            "צרכן רשאי לבטל עסקה תוך 14 ימים מיום קבלת המוצר. "
            "הצרכן רשאי לבטל את העסקה בכתב, בטלפון או בכל דרך אחרת. "
            "במקרה של ביטול, החנות חייבת להחזיר את מלוא הסכום ששולם תוך 14 ימי עסקים."
        ),
        "url": "https://www.gov.il/he/pages/consumer-protection-cancellation",
        "category": "הגנת הצרכן",
        "document_type": "regulation",
        "published_date": "2010",
        "source_id": "CP-2010-001",
    },
    {
        "title": "חוק הגנת הצרכן, התשמ\"א-1981",
        "content": (
            "חוק הגנת הצרכן מגן על הצרכן מפני עוסקים הפועלים בדרך לא הוגנת. "
            "החוק אוסר על הטעיה, כפייה ועושק בעסקאות עם צרכנים. "
            "הרשות להגנת הצרכן מוסמכת להטיל קנסות על עוסקים המפרים את החוק. "
            "תקנות נוספות נקבעו מכוח החוק לעניין גילוי מחירים, אחריות ושירות."
        ),
        "url": "https://www.gov.il/he/pages/consumer-protection-law-1981",
        "category": "הגנת הצרכן",
        "document_type": "law",
        "published_date": "1981",
        "source_id": "CP-1981-001",
    },
    {
        "title": "תקנות התכנון והבנייה (רישוי בנייה), התשע\"ו-2016",
        "content": (
            "תקנות אלה מסדירות את הליך הוצאת היתר בנייה בישראל. "
            "בקשה להיתר בנייה תוגש לוועדה המקומית לתכנון ובנייה. "
            "הבקשה תכלול תכניות אדריכליות, חישובים סטטיים ואישורים נדרשים. "
            "הוועדה תדון בבקשה תוך 45 ימי עסקים מיום הגשתה. "
            "בנייה ללא היתר עלולה לגרור צו הריסה וקנסות כבדים."
        ),
        "url": "https://www.gov.il/he/pages/planning-building-permits-2016",
        "category": "תכנון ובנייה",
        "document_type": "regulation",
        "published_date": "2016",
        "source_id": "PB-2016-001",
    },
    {
        "title": "חוק עבודת נשים, התשי\"ד-1954",
        "content": (
            "חוק עבודת נשים מגן על זכויות עובדות בישראל. "
            "החוק אוסר על פיטורי עובדת בהריון ללא אישור הממונה על חוק עבודת נשים. "
            "עובדת זכאית לחופשת לידה בתשלום של 26 שבועות. "
            "המעביד אינו רשאי לפגוע בשכר עובדת בשל הריון, לידה או שמירת הריון. "
            "הפרת החוק מהווה עבירה פלילית."
        ),
        "url": "https://www.gov.il/he/pages/women-employment-law-1954",
        "category": "דיני עבודה",
        "document_type": "law",
        "published_date": "1954",
        "source_id": "WE-1954-001",
    },
    {
        "title": "תקנות בריאות הציבור (מזון) (סימון מזון), התשנ\"ג-1993",
        "content": (
            "תקנות אלה קובעות את חובות סימון המזון על גבי אריזות. "
            "כל מוצר מזון חייב לנשוא תווית עם שם המוצר, רשימת מרכיבים, ערכים תזונתיים, "
            "תאריך תפוגה ושם היצרן. "
            "סימון כשרות חייב להיעשות בהתאם להוראות הרבנות הראשית. "
            "מוצרים המכילים אלרגנים חייבים בסימון מפורש. "
            "עסק המפר את תקנות הסימון צפוי לקנסות ולסגירת העסק."
        ),
        "url": "https://www.gov.il/he/pages/food-labeling-regulations-1993",
        "category": "בריאות הציבור",
        "document_type": "regulation",
        "published_date": "1993",
        "source_id": "PH-1993-001",
    },
    {
        "title": "חוק חינוך חובה, התש\"ט-1949",
        "content": (
            "חוק חינוך חובה קובע חינוך חינם וחובה לילדים בגיל 3 עד 18. "
            "ההורים חייבים לדאוג לרישום ילדיהם למוסד חינוך מוכר. "
            "המדינה מממנת את החינוך היסודי והעל-יסודי במוסדות ממלכתיים. "
            "הפרת חוק חינוך חובה עלולה לגרור קנסות על ההורים. "
            "משרד החינוך פוקח על יישום החוק בכלל הרשויות המקומיות."
        ),
        "url": "https://www.gov.il/he/pages/compulsory-education-law-1949",
        "category": "חינוך",
        "document_type": "law",
        "published_date": "1949",
        "source_id": "ED-1949-001",
    },
    {
        "title": "תקנות התעבורה, התשכ\"א-1961",
        "content": (
            "תקנות התעבורה מסדירות את הכללים לנהיגה בטוחה בכבישים. "
            "מהירות מירבית בכביש עירוני היא 50 קמ\"ש, ובכביש בין-עירוני 90 קמ\"ש. "
            "חובה לחגור חגורת בטיחות בכל מושב ברכב. "
            "שימוש בטלפון נייד בנהיגה ללא דיבורית אסור ומהווה עבירה קנסית. "
            "נהיגה בשכרות עלולה לגרור שלילת רישיון ועונש מאסר."
        ),
        "url": "https://www.gov.il/he/pages/traffic-regulations-1961",
        "category": "תחבורה",
        "document_type": "regulation",
        "published_date": "1961",
        "source_id": "TR-1961-001",
    },
    {
        "title": "חוק הביטוח הלאומי [נוסח משולב], התשנ\"ה-1995",
        "content": (
            "חוק הביטוח הלאומי מסדיר את מערכת ביטוח הסיעוד, נכות, דמי אבטלה ותגמולים. "
            "כל עובד שכיר ועצמאי חייב בתשלום דמי ביטוח לאומי. "
            "הזכאות לקצבאות נקבעת לפי קריטריונים מוגדרים בחוק. "
            "המוסד לביטוח לאומי מפעיל מוקד שירות לבירורים ותביעות. "
            "ניתן להגיש ערר על החלטת המוסד לביטוח לאומי בפני ועדת הערר."
        ),
        "url": "https://www.gov.il/he/pages/national-insurance-law-1995",
        "category": "ביטוח לאומי",
        "document_type": "law",
        "published_date": "1995",
        "source_id": "NI-1995-001",
    },
    {
        "title": "תקנות מס הכנסה (כללים לאישור ולניהול קופות גמל), התשכ\"ד-1964",
        "content": (
            "תקנות אלה קובעות את הכללים לאישור ולניהול קופות גמל. "
            "קופת גמל חייבת לנהל חשבון נפרד לכל עמית. "
            "דמי הגמולים מועברים על ידי המעביד מדי חודש. "
            "עמית רשאי למשוך את כספי הקופה בפרישה לגמלאות או בנסיבות מיוחדות. "
            "רווחים בקופת גמל פטורים ממס עד לתקרה הקבועה בחוק."
        ),
        "url": "https://www.gov.il/he/pages/provident-fund-regulations-1964",
        "category": "פיננסים ומיסוי",
        "document_type": "regulation",
        "published_date": "1964",
        "source_id": "FIN-1964-001",
    },
    {
        "title": "חוק הגנת הפרטיות, התשמ\"א-1981",
        "content": (
            "חוק הגנת הפרטיות מגן על הזכות לפרטיות של כל אדם בישראל. "
            "האוסף מידע על אנשים ומנהל מאגר מידע חייב לרשום אותו ברשות לאומית להגנת מידע. "
            "אסור לעשות שימוש במידע אישי שלא למטרה שלשמה נאסף. "
            "כל אדם רשאי לעיין במידע המוחזק עליו ולבקש תיקונו. "
            "הפרת החוק עלולה לגרור תביעה אזרחית ועונש פלילי."
        ),
        "url": "https://www.gov.il/he/pages/privacy-protection-law-1981",
        "category": "הגנת הפרטיות",
        "document_type": "law",
        "published_date": "1981",
        "source_id": "PP-1981-001",
    },
    {
        "title": "תקנות רישוי עסקים (הוראות כלליות), התשס\"א-2000",
        "content": (
            "תקנות אלה קובעות את הכללים לקבלת רישיון עסק בישראל. "
            "כל עסק הטעון רישוי חייב להגיש בקשה לרשות המקומית. "
            "הבקשה מלווה בחוות דעת של גורמים כגון כבאות, משטרה, משרד הבריאות ומשרד הסביבה. "
            "רישיון עסק מוצא לתקופה קצובה ומחייב חידוש. "
            "עסק הפועל ללא רישיון צפוי לקנסות ולצו סגירה."
        ),
        "url": "https://www.gov.il/he/pages/business-licensing-regulations-2000",
        "category": "רישוי עסקים",
        "document_type": "regulation",
        "published_date": "2000",
        "source_id": "BL-2000-001",
    },
    {
        "title": "חוק שוויון זכויות לאנשים עם מוגבלות, התשנ\"ח-1998",
        "content": (
            "החוק קובע כי אנשים עם מוגבלות זכאים לשוויון זכויות בכל תחומי החיים. "
            "מעסיקים חייבים לבצע התאמות סבירות לעובדים עם מוגבלות. "
            "שירותים ציבוריים חייבים להיות נגישים לאנשים עם מוגבלות. "
            "הנציבות לשוויון זכויות לאנשים עם מוגבלות מטפלת בתלונות. "
            "הפרת החוק מהווה עילה לתביעה אזרחית."
        ),
        "url": "https://www.gov.il/he/pages/disability-rights-law-1998",
        "category": "זכויות אדם",
        "document_type": "law",
        "published_date": "1998",
        "source_id": "DR-1998-001",
    },
]


def seed():
    Base.metadata.create_all(bind=engine)

    db = SessionLocal()
    added = 0
    skipped = 0

    try:
        for doc_data in SAMPLE_DOCS:
            existing = db.query(Document).filter(Document.url == doc_data["url"]).first()
            if existing:
                skipped += 1
                continue
            doc = Document(**doc_data)
            db.add(doc)
            added += 1

        db.commit()

        # Refresh search vectors
        db.execute(
            text(
                """
                UPDATE documents
                SET search_vector =
                    setweight(to_tsvector('simple', COALESCE(title, '')), 'A') ||
                    setweight(to_tsvector('simple', COALESCE(content, '')), 'B')
                WHERE search_vector IS NULL
                """
            )
        )
        db.commit()

        print(f"✅ Seed complete: {added} added, {skipped} already existed.")
    except Exception as e:
        db.rollback()
        print(f"❌ Seed failed: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    seed()
