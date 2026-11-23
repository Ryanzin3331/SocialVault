package br.com.socialvault.app;

import static org.junit.Assert.*;
import org.junit.Test;

public class TikTokLinkTest {
    @Test public void receivesShareText() {
        assertEquals("https://vt.tiktok.com/ZSTest/",
            TikTokLink.extract("Vídeo legal! https://vt.tiktok.com/ZSTest/ abre aí"));
    }
    @Test public void acceptsDirectVideo() {
        assertEquals("https://www.tiktok.com/@teste/video/123",
            TikTokLink.extract("https://www.tiktok.com/@teste/video/123"));
    }
    @Test public void rejectsImpersonators() {
        assertNull(TikTokLink.extract("https://tiktok.com.evil.test/abc"));
        assertNull(TikTokLink.extract("https://tiktok.com@evil.test/abc"));
        assertNull(TikTokLink.extract("https://vt.tiktok.com:8443/a"));
    }
    @Test public void rejectsNonTikTok() {
        assertNull(TikTokLink.extract("https://example.org/watch?v=7"));
        assertNull(TikTokLink.extract("um texto qualquer"));
    }
    @Test public void picksOfficialUrl() {
        assertEquals("https://vm.tiktok.com/ZSTest/",
            TikTokLink.extract("https://not-tiktok.com/x https://vm.tiktok.com/ZSTest/."));
    }
}
