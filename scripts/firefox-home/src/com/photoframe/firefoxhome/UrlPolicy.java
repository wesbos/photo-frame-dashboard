package com.photoframe.firefoxhome;

import java.net.URI;
import java.net.URISyntaxException;

/** Shared validation for both new and previously saved dashboard URLs. */
final class UrlPolicy {
    static String normalize(String value) {
        if (value == null) return "";
        String url = value.trim();
        try {
            URI uri = new URI(url);
            String scheme = uri.getScheme();
            if (("http".equalsIgnoreCase(scheme) || "https".equalsIgnoreCase(scheme))
                    && uri.getHost() != null && !uri.getHost().isEmpty()) return url;
        } catch (URISyntaxException e) {
            // Invalid input must not overwrite a working dashboard.
        }
        return "";
    }
}
