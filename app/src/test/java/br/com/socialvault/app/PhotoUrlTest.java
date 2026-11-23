package br.com.socialvault.app;

import org.junit.Test;
import static org.junit.Assert.*;

public class PhotoUrlTest {
    @Test public void permitsHttpsCdn() {
        assertTrue(PhotoUrl.isSafe("https://p16-sign.tiktokcdn.com/preview.jpg?x=1"));
    }
    @Test public void rejectsHttpAndLocal() {
        assertFalse(PhotoUrl.isSafe("http://p16-sign.tiktokcdn.com/a.jpg"));
        assertFalse(PhotoUrl.isSafe("https://localhost/a.jpg"));
        assertFalse(PhotoUrl.isSafe("https://127.0.0.1/a.jpg"));
        assertFalse(PhotoUrl.isSafe("https://192.168.1.12/a.jpg"));
        assertFalse(PhotoUrl.isSafe("https://server.local/a.jpg"));
        assertFalse(PhotoUrl.isSafe("https://user:pass@cdn.example.com/a.jpg"));
    }
    @Test public void rejectsInvalid() {
        assertFalse(PhotoUrl.isSafe(null));
        assertFalse(PhotoUrl.isSafe("ftp://cdn.example.com/a.jpg"));
        assertFalse(PhotoUrl.isSafe("broken"));
        assertFalse(PhotoUrl.isSafe("https://cdn.example.com:8080/a.jpg"));
    }
}
