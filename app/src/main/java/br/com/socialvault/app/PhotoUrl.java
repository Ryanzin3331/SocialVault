package br.com.socialvault.app;

import java.net.URI;
import java.util.Locale;

/** Strict HTTPS policy for CDN media returned by the TikTok photo extractor. */
public final class PhotoUrl {
    private PhotoUrl() { }

    public static boolean isSafe(String source) {
        if (source == null || source.length() > 5000) return false;
        try {
            URI uri = URI.create(source);
            if (!"https".equalsIgnoreCase(uri.getScheme())) return false;
            if (uri.getUserInfo() != null || uri.getPort() != -1) return false;
            String host = uri.getHost();
            if (host == null || host.isEmpty()) return false;
            host = host.toLowerCase(Locale.US);
            if (host.equals("localhost") || host.endsWith(".localhost")
                    || host.endsWith(".local") || host.endsWith(".internal")) return false;
            // Metadata should return CDN hostnames, never literal IP addresses.
            if (host.matches("[0-9.]+") || host.contains(":")) return false;
            return host.contains(".");
        } catch (IllegalArgumentException error) {
            return false;
        }
    }
}
