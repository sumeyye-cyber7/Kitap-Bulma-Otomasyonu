import customtkinter as ctk  # Modern ve koyu tema destekli arayüz kütüphanesi
import webbrowser  # Tarayıcıda web sitesi açmak için
import requests  # İnternetten (API) veri çekmek için
from tkinter import messagebox  # Ekrana uyarı/hata mesajı kutusu çıkarmak için
from PIL import Image  # Görsel işleme kütüphanesi
from io import BytesIO  # İnternetten inen görsel verisini bellekte işlemek için
import random  # Rastgele kitap seçimi için
import threading  # Arayüzün donmasını engellemek için arka plan iş parçacığı kütüphanesi
import urllib.parse  # Metinleri internet adreslerine (URL) uygun formata çevirir

# --- ÇEVİRİ KÜTÜPHANESİ KONTROLÜ ---
try:
    from deep_translator import GoogleTranslator  # Çeviri kütüphanesini yükle

    TRANSLATOR_OK = True  # Kütüphane varsa çeviri sistemini aktif et
except ImportError:
    TRANSLATOR_OK = False  # Kütüphane yoksa sistemi kapat, programın çökmesini önlea

# --- GENEL AYARLAR ---
ctk.set_appearance_mode("Dark")  # Varsayılan temayı karanlık mod yapar
ctk.set_default_color_theme("blue")  # Temanın vurgu rengini mavi yapar

# Open Library API internet adresleri
OL_SEARCH = "https://openlibrary.org/search.json"  # Arama adresi
OL_WORKS = "https://openlibrary.org"  # Detay ve özet adresi
OL_COVER_ID = "https://covers.openlibrary.org/b/id/{}-L.jpg"  # Kapak resmi adresi

# Ruh hallerine göre eşleşen İngilizce/Türkçe anahtar kelimeler
MOOD_MAP = {
    "mutlu": ["happiness", "joy", "comedy", "humor", "uplifting", "mizah"],
    "üzgün": ["healing", "hope", "grief", "inspirational", "dram", "umut"],
    "heyecanlı": ["thriller", "suspense", "action", "mystery", "macera", "gerilim"],
    "yorgun": ["cozy", "relaxing", "gentle", "light fiction", "sakin", "huzur"],
    "maceracı": ["adventure", "fantasy", "quest", "epic", "kesif", "fantastik"],
    "romantik": ["romance", "love story", "ask", "romantik", "duygusal"],
    "düşünceli": ["philosophy", "psychology", "deep meaning", "felsefe", "dusunce"],
    "korku": ["horror", "ghost", "supernatural", "scary", "korku", "gizem"],
    "meraklı": ["science", "discovery", "history", "biography", "bilim", "tarih"],
    "default": ["popular novel", "classic literature", "roman"]
}

HEADERS = {"User-Agent": "KitapAsistani"}  # API istekleri için kimlik başlığı


# --- YARDIMCI FONKSİYONLAR ---

def turkce_cevir(metin: str) -> str:
    """Gelen İngilizce metni Google Çeviri ile Türkçeye dönüştürür."""
    if not metin or not TRANSLATOR_OK:
        return metin
    try:
        # Eğer metin kısa bir etiket listesiyse kelime kelime çevirir
        if "," in metin and len(metin) < 200:
            parcalar = [p.strip() for p in metin.split(",")]
            ceviriler = [GoogleTranslator(source="auto", target="tr").translate(p) for p in parcalar[:5]]
            return ", ".join(filter(None, ceviriler))

        # Uzun özet metinlerini çevirir (Karakter sınırına takılmamak için ilk 4500 harf)
        return GoogleTranslator(source="auto", target="tr").translate(metin[:4500])
    except:
        return metin  # Hata durumunda orijinal metni döndür


def fetch_image(url: str, size: tuple) -> ctk.CTkImage:
    """İnternetteki resmi indirip arayüze uygun formata getirir."""
    try:
        if url:
            r = requests.get(url, headers=HEADERS, timeout=15)  # Resmi indir
            if r.status_code == 200 and len(r.content) > 500:  # Görsel geçerliyse işle
                img = Image.open(BytesIO(r.content)).convert("RGB")
                return ctk.CTkImage(light_image=img, dark_image=img, size=size)
    except Exception as e:
        print(f"Resim yükleme hatası: {e}")

    # Resim bulunamazsa veya hata oluşursa lacivert boş bir şablon döndürür
    p_img = Image.new("RGB", size, color=(30, 35, 50))
    return ctk.CTkImage(light_image=p_img, dark_image=p_img, size=size)


def parse_book(doc: dict):
    """API'den gelen ham verileri ayıklayıp düzenli bir sözlüğe dönüştürür."""
    title = doc.get("title", "Bilinmiyor")
    cover_id = doc.get("cover_i")

    # Sayfa sayısını farklı veri alanlarını kontrol ederek çeker
    page_count = doc.get("number_of_pages_median") or doc.get("number_of_pages")
    if isinstance(page_count, list) and page_count:
        page_count = page_count[0]

    subjects = doc.get("subject", [])

    return {
        "title": title,
        "authors": ", ".join(doc.get("author_name", ["Bilinmiyor"])),
        "year": str(doc.get("first_publish_year", "Bilinmiyor")),
        "pages": str(page_count) if page_count else "Belirtilmemiş",
        "publisher": ", ".join(doc.get("publisher", ["Bilinmiyor"])[:2]),
        "key": doc.get("key"),  # Kitabın benzersiz kimlik kodu
        "first_subject": subjects[0] if subjects else None,  # Benzer kitap araması için ana kategori
        "subjects": ", ".join(subjects[:5]),
        "cover_url": OL_COVER_ID.format(cover_id) if cover_id else None
    }


# --- BİLEŞENLER ---

class BookCard(ctk.CTkFrame):
    """Alt kısımda yan yana dizilen küçük kitap kartı bileşeni."""

    def __init__(self, master, book, on_click):
        super().__init__(master, fg_color="#161b2e", corner_radius=10, width=150, height=230, cursor="hand2")
        self.pack_propagate(False)  # İçerik taşsa bile kart boyutunu sabit tutar
        self.book = book

        # Kapak görsel alanı (Resim yüklenene kadar bekletme simgesi gösterir)
        self.img_lbl = ctk.CTkLabel(self, text="⌛", height=160, fg_color="#0a0c15", corner_radius=8)
        self.img_lbl.pack(pady=6, padx=8, fill="x")

        # Uzun kitap isimlerini kırparak ekler
        short_title = (book["title"][:16] + "..") if len(book["title"]) > 16 else book["title"]
        self.title_lbl = ctk.CTkLabel(self, text=short_title, font=("Arial", 11, "bold"), text_color="#ffffff")
        self.title_lbl.pack(pady=1, padx=4)

        # Uzun yazar isimlerini kırparak ekler
        short_author = (book["authors"][:18] + "..") if len(book["authors"]) > 18 else book["authors"]
        self.author_lbl = ctk.CTkLabel(self, text=short_author, font=("Arial", 10), text_color="gray")
        self.author_lbl.pack(padx=4)

        # Karta veya içindeki elemanlara tıklandığında tıklama fonksiyonunu çalıştırır
        self.bind("<Button-1>", lambda e: on_click(book))
        for child in self.winfo_children():
            child.bind("<Button-1>", lambda e: on_click(book))

        # Resmi arka planda indirmek için yeni iş parçacığı başlatır
        threading.Thread(target=self.load_img, daemon=True).start()

    def load_img(self):
        """Arka planda resmi indirip ekrandaki karta yerleştirir."""
        img = fetch_image(self.book["cover_url"], (130, 160))
        self.img_lbl.img_cache = img  # Resmin hafızadan silinmesini önler
        self.after(0, lambda: self.img_lbl.configure(image=img, text=""))  # Ana arayüzde resmi günceller


# --- ANA UYGULAMA ---

class KitapAsistani(ctk.CTk):
    """Uygulama pencerelerini ve arama motoru mantığını yöneten ana sınıf."""

    def __init__(self):
        super().__init__()
        self.title("📚 Yapay Zeka Destekli Kitap Asistanı Pro")
        self.geometry("1300x890")

        self.setup_ui()  # Arayüzü inşa eder

    def setup_ui(self):
        """Sol menüyü ve sağ sekmeli panelleri oluşturur."""
        # Sol Menü Paneli (Sidebar)
        self.sidebar = ctk.CTkFrame(self, width=220, corner_radius=0)
        self.sidebar.pack(side="left", fill="y")

        ctk.CTkLabel(self.sidebar, text="KİTAP ASİSTANI", font=("Georgia", 18, "bold"), text_color="#3b82f6").pack(
            pady=30)

        # Menü yönlendirme butonları
        ctk.CTkButton(self.sidebar, text="🔍 Kitap Ara / Bul", command=lambda: self.tab_view.set("Arama")).pack(pady=10,
                                                                                                               padx=20)
        ctk.CTkButton(self.sidebar, text="✨ Ruh Hali Önerisi", command=lambda: self.tab_view.set("Ruh Hali")).pack(
            pady=10, padx=20)
        ctk.CTkButton(self.sidebar, text="🛒 BKM Kitap'ta Ara", fg_color="#7a2d1a", hover_color="#5a2012",
                      command=self.open_bkm).pack(pady=10, padx=20)

        # Sağ Alan Sekme Yapısı
        self.tab_view = ctk.CTkTabview(self, fg_color="transparent")
        self.tab_view.pack(side="right", fill="both", expand=True, padx=10, pady=10)
        self.tab_view.add("Arama")
        self.tab_view.add("Ruh Hali")

        self.setup_search_tab()  # Arama sekmesini kurar
        self.setup_mood_tab()  # Ruh hali sekmesini kurar

    def setup_search_tab(self):
        """Arama sekmesinin iç tasarımını yapar."""
        tab = self.tab_view.tab("Arama")

        # Üst Arama Çubuğu
        top = ctk.CTkFrame(tab, fg_color="transparent")
        top.pack(fill="x", pady=10)

        self.search_entry = ctk.CTkEntry(top,
                                         placeholder_text="Kitap adı veya yazar ismi girin (Örn: Sabahattin Ali)...",
                                         height=45)
        self.search_entry.pack(side="left", fill="x", expand=True, padx=(0, 10))
        self.search_entry.bind("<Return>", lambda e: self.search_by_query())  # Enter tuşu bağlantısı

        ctk.CTkButton(top, text="Kitabı Bul", width=120, height=45, command=self.search_by_query).pack(side="left")

        # Orta Detay Paneli (Kapak + Bilgiler)
        detail_frame = ctk.CTkFrame(tab, fg_color="#1a1c26")
        detail_frame.pack(fill="both", expand=True, pady=10)

        self.search_cover = ctk.CTkLabel(detail_frame, text="Kitap Kapağı", width=220, height=310, fg_color="#0a0c15",
                                         corner_radius=10)
        self.search_cover.pack(side="left", padx=20, pady=20)

        self.search_info_text = ctk.CTkTextbox(detail_frame, font=("Arial", 14), wrap="word")
        self.search_info_text.pack(side="left", fill="both", expand=True, padx=(0, 20), pady=20)

        # Alt Alan (Benzer Kitaplar Şeridi)
        self.search_similar_lbl = ctk.CTkLabel(tab, text="Bu Kitabı Sevdiyseniz Bunlara da Bakabilirsiniz:",
                                               font=("Arial", 14, "bold"))
        self.search_similar_lbl.pack(anchor="w", pady=(5, 0))

        self.search_similar_scroll = ctk.CTkScrollableFrame(tab, orientation="horizontal", height=250,
                                                            fg_color="transparent")
        self.search_similar_scroll.pack(fill="x", pady=5)

    def setup_mood_tab(self):
        """Ruh hali sekmesinin iç tasarımını yapar."""
        tab = self.tab_view.tab("Ruh Hali")

        # Üst Arama Çubuğu
        top = ctk.CTkFrame(tab, fg_color="transparent")
        top.pack(fill="x", pady=10)

        self.mood_entry = ctk.CTkEntry(top,
                                       placeholder_text="Şu anki hissiniz? (mutlu, yorgun, maceracı, romantik, korku...)",
                                       height=45)
        self.mood_entry.pack(side="left", fill="x", expand=True, padx=(0, 10))
        self.mood_entry.bind("<Return>", lambda e: self.search_by_mood())  # Enter tuşu bağlantısı

        ctk.CTkButton(top, text="Bana Özel Kitap Keşfet ✨", width=200, height=45, fg_color="#2563eb",
                      command=self.search_by_mood).pack(side="left")

        # Orta Detay Paneli (Kapak + Bilgiler)
        detail_frame = ctk.CTkFrame(tab, fg_color="#1e1b26")
        detail_frame.pack(fill="both", expand=True, pady=10)

        self.mood_cover = ctk.CTkLabel(detail_frame, text="Öneri Kapağı", width=220, height=310, fg_color="#0a0c15",
                                       corner_radius=10)
        self.mood_cover.pack(side="left", padx=20, pady=20)

        self.mood_info_text = ctk.CTkTextbox(detail_frame, font=("Arial", 14), wrap="word")
        self.mood_info_text.pack(side="left", fill="both", expand=True, padx=(0, 20), pady=20)

        # Alt Alan (Benzer Öneriler Şeridi)
        self.mood_similar_lbl = ctk.CTkLabel(tab, text="Bu Öneriyi Beğendiyseniz Aynı Türdeki Diğer Seçenekler:",
                                             font=("Arial", 14, "bold"))
        self.mood_similar_lbl.pack(anchor="w", pady=(5, 0))

        self.mood_similar_scroll = ctk.CTkScrollableFrame(tab, orientation="horizontal", height=250,
                                                          fg_color="transparent")
        self.mood_similar_scroll.pack(fill="x", pady=5)

    # --- KONTROL VE ARKA PLAN İŞLEMLERİ ---

    def search_by_query(self):
        """Normal kitap araması yapıldığında tetiklenir."""
        term = self.search_entry.get().strip()
        if not term: return

        self.search_info_text.delete("1.0", "end")
        self.search_info_text.insert("end",
                                     "🔍 Kitap detayları doğrulanıyor ve Türkçe kaynaklar taranıyor. Lütfen bekleyin...")

        # Arama motorunu arka planda çalıştırır
        threading.Thread(target=self.process_book_search, args=(term, False, "search"), daemon=True).start()

    def search_by_mood(self):
        """Ruh haline göre arama yapıldığında tetiklenir."""
        mood = self.mood_entry.get().lower().strip()
        if not mood: return

        self.mood_info_text.delete("1.0", "end")
        self.mood_info_text.insert("end",
                                   f"✨ Ruh halinize uygun rastgele bir Türkçe/Evrensel kitap kombinasyonu getiriliyor...")

        # Havuzdan rastgele bir alt kategori seçer ve aramayı arka planda başlatır
        queries = MOOD_MAP.get(mood, MOOD_MAP["default"])
        selected_query = random.choice(queries)
        threading.Thread(target=self.process_book_search, args=(selected_query, True, "mood"), daemon=True).start()

    def process_book_search(self, term, is_genre_search, mode):
        """API isteklerini yöneten ve veriyi işleyen ana fonksiyon."""
        try:
            # İstek atılacak internet adresini (URL) hazırlar
            if is_genre_search:
                random_page = random.randint(1, 4)
                url = f"{OL_SEARCH}?q={urllib.parse.quote(term)}&page={random_page}&limit=15"
            else:
                url = f"{OL_SEARCH}?q={urllib.parse.quote(term)}&limit=5"

            r = requests.get(url, headers=HEADERS, timeout=15)
            docs = r.json().get("docs", [])

            if not docs:
                self.after(0, lambda: self.clear_and_show_error(mode,
                                                                "❌ Aradığınız kriterlere uygun kitap kaydı bulunamadı."))
                return

            # Türkçe veya rastgele kitap seçme algoritması
            selected_doc = docs[0]
            if is_genre_search:
                selected_doc = random.choice(docs)
            else:
                for doc in docs:
                    if "tur" in doc.get("language", []):
                        selected_doc = doc
                        break

            main_book = parse_book(selected_doc)

            # Detaylı kitap özeti çekme ve Türkçeye çevirme aşaması
            desc_tr = "Bu eser için sisteme girilmiş detaylı bir özet bulunamadı."
            if main_book["key"]:
                res = requests.get(f"{OL_WORKS}{main_book['key']}.json", headers=HEADERS, timeout=10).json()
                desc_raw = res.get("description", "")
                if isinstance(desc_raw, dict):
                    desc_raw = desc_raw.get("value", "")
                if desc_raw:
                    desc_tr = turkce_cevir(desc_raw)

            # Benzer kitapları filtreleyerek listeye toplama aşaması
            similars = []
            subject_query = main_book["first_subject"] or term
            safe_subject = urllib.parse.quote(subject_query)

            sub_res = requests.get(f"{OL_SEARCH}?q={safe_subject}&limit=15", headers=HEADERS, timeout=10).json()
            sub_docs = sub_res.get("docs", [])

            for d in sub_docs:
                parsed = parse_book(d)
                # Aynı kitabın tekrar listelenmesini engeller ve kapağı olanları seçer
                if parsed["title"].lower() != main_book["title"].lower() and main_book["title"].lower() not in parsed[
                    "title"].lower():
                    if parsed["cover_url"]:
                        similars.append(parsed)
                if len(similars) >= 6:
                    break

            # Kapaklı benzer kitap azsa kapaksızları da listeye dahil eder
            if len(similars) < 3:
                for d in sub_docs:
                    parsed = parse_book(d)
                    if parsed["title"].lower() != main_book["title"].lower() and parsed not in similars:
                        similars.append(parsed)
                    if len(similars) >= 6:
                        break

            # Ekrandaki metin şablonunu oluşturur
            info = f"📖 KİTAP ADI: {main_book['title']}\n"
            info += f"──────────────────────────────────────────\n"
            info += f"✍️ YAZAR(LAR): {main_book['authors']}\n"
            info += f"📅 İLK BASIM YILI: {main_book['year']}\n"
            info += f"📄 SAYFA SAYISI: {main_book['pages']}\n"
            info += f"🏢 YAYINEVİ: {main_book['publisher']}\n"
            info += f"🏷️ KONULAR / TÜRLER: {turkce_cevir(main_book['subjects'])}\n"
            info += f"──────────────────────────────────────────\n"
            info += f"📝 KİTAP ÖZETİ:\n{desc_tr}"

            img = fetch_image(main_book["cover_url"], (220, 310))

            # Verileri ekrana basması için ana arayüz iş parçacığına gönderir
            self.after(0, lambda: self.update_ui_elements(mode, info, img, similars, main_book["title"]))

        except Exception as e:
            print(f"Hata: {e}")
            self.after(0, lambda: messagebox.showerror("Bağlantı Hatası", "Veriler işlenirken hata oluştu."))

    def update_ui_elements(self, mode, info, img, similars, title):
        """Aktif sekmeye göre panelleri doldurur ve alt kartları ekler."""
        if mode == "search":
            txt_area = self.search_info_text
            cov_area = self.search_cover
            scroll_area = self.search_similar_scroll
            lbl_area = self.search_similar_lbl
            click_callback = lambda b: self.load_card_book(b, "search")
        else:
            txt_area = self.mood_info_text
            cov_area = self.mood_cover
            scroll_area = self.mood_similar_scroll
            lbl_area = self.mood_similar_lbl
            click_callback = lambda b: self.load_card_book(b, "mood")

        txt_area.delete("1.0", "end")
        txt_area.insert("end", info)  # Metni yazar

        cov_area.img_ref = img
        cov_area.configure(image=img, text="")  # Kapağı yerleştirir

        for child in scroll_area.winfo_children():
            child.destroy()  # Eski küçük kartları temizler

        lbl_area.configure(text=f"'{title}' Eserini Beğendiyseniz Bu Benzer Konulu Kitaplara da Bakabilirsiniz:")

        # Benzer kitap kartlarını oluşturup yan yana dizer
        if similars:
            for b in similars:
                card = BookCard(scroll_area, b, click_callback)
                card.pack(side="left", padx=10, pady=5)
        else:
            ctk.CTkLabel(scroll_area, text="Aynı kategoriye ait başka benzer kitap eşleşmesi bulunamadı.",
                         font=("Arial", 12, "italic")).pack(pady=20, padx=20)

    def load_card_book(self, book_dict, mode):
        """Küçük bir benzer kitap kartına tıklandığında onu büyük detay paneline taşır."""
        if mode == "search":
            self.search_info_text.delete("1.0", "end")
            self.search_info_text.insert("end", "🔍 Seçilen kitap detayları getiriliyor...")
        else:
            self.mood_info_text.delete("1.0", "end")
            self.mood_info_text.insert("end", "🔍 Seçilen kitap detayları getiriliyor...")

        # Seçilen kitabın detaylarını arka planda aramaya gönderir
        threading.Thread(target=self.process_book_search, args=(book_dict["title"], False, mode), daemon=True).start()

    def clear_and_show_error(self, mode, msg):
        """Sonuç bulunamadığında ekrana uyarı mesajını basar."""
        target = self.search_info_text if mode == "search" else self.mood_info_text
        target.delete("1.0", "end")
        target.insert("end", msg)

    def open_bkm(self):
        """Aktif sekmedeki kelimeyi alır ve BKM Kitap web sitesinde aratır."""
        current_tab = self.tab_view.get()
        q = self.search_entry.get().strip() if current_tab == "Arama" else self.mood_entry.get().strip()

        if q:
            webbrowser.open(f"https://www.bkmkitap.com/arama?q={urllib.parse.quote(q)}")
        else:
            messagebox.showwarning("Uyarı", "Lütfen önce geçerli bir arama metni girin.")


# --- PROGRAMIN BAŞLANGIÇ NOKTASI ---
if __name__ == "__main__":
    app = KitapAsistani()
    app.mainloop()  # Pencereyi kapatana kadar döngüyü açık tutar