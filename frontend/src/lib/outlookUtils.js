/**
 * Outlook Web integration utilities
 * Generates deep links to create email drafts in Outlook Web
 */

/**
 * Generate an Outlook Web deep link to compose a new email with pre-filled content
 *
 * @param {string} messageContent - The message content to insert into the email body
 * @param {string} subject - Optional email subject
 * @returns {string} Outlook Web compose URL
 */
export function generateOutlookDraftUrl(messageContent, subject = "") {
  // Outlook Web compose deep link format
  const baseUrl = "https://outlook.office.com/mail/deeplink/compose";

  if (!messageContent && !subject) {
    return baseUrl;
  }

  // Convert markdown to plain text for email body
  const plainText = messageContent ? convertMarkdownToPlainText(messageContent) : "";

  // Build query parameters manually using encodeURIComponent
  // This ensures proper encoding that Outlook Web will decode correctly
  const params = [];

  if (subject) {
    params.push(`subject=${encodeURIComponent(subject)}`);
  }

  if (plainText) {
    params.push(`body=${encodeURIComponent(plainText)}`);
  }

  // Build the full URL
  const url = params.length > 0 ? `${baseUrl}?${params.join("&")}` : baseUrl;

  return url;
}

/**
 * Convert markdown to plain text
 * Removes common markdown formatting for better email compatibility
 *
 * @param {string} markdown - Markdown text
 * @returns {string} Plain text
 */
function convertMarkdownToPlainText(markdown) {
  if (!markdown) return "";

  let text = markdown;

  // Remove code blocks (```...```)
  text = text.replace(/```[\s\S]*?```/g, (match) => {
    return match.replace(/```\w*\n?/g, "").replace(/```/g, "");
  });

  // Remove inline code (`...`)
  text = text.replace(/`([^`]+)`/g, "$1");

  // Remove bold/italic (**...**, *...*, __...__, _..._)
  text = text.replace(/(\*\*|__)(.*?)\1/g, "$2");
  text = text.replace(/(\*|_)(.*?)\1/g, "$2");

  // Remove headers (# ... \n)
  text = text.replace(/^#{1,6}\s+(.*)$/gm, "$1");

  // Remove links but keep text ([text](url) -> text)
  text = text.replace(/\[([^\]]+)\]\([^\)]+\)/g, "$1");

  // Remove images (![alt](url) -> alt)
  text = text.replace(/!\[([^\]]*)\]\([^\)]+\)/g, "$1");

  // Remove horizontal rules (---, ***, ___)
  text = text.replace(/^(\*\*\*|---|___)$/gm, "");

  // Remove blockquotes (> ...)
  text = text.replace(/^>\s+(.*)$/gm, "$1");

  // Remove list markers (-, *, +, 1.)
  text = text.replace(/^[\s]*[-*+]\s+/gm, "");
  text = text.replace(/^[\s]*\d+\.\s+/gm, "");

  return text.trim();
}

/**
 * Open Outlook Web with a draft email
 * Attempts to open in a new tab, with fallback to clipboard
 *
 * @param {string} messageContent - The message content
 * @param {string} subject - Optional email subject
 * @returns {Promise<boolean>} True if successful, false if fallback used
 */
export async function openOutlookDraft(messageContent, subject = "") {
  try {
    const url = generateOutlookDraftUrl(messageContent, subject);

    // Attempt to open in new tab
    const newWindow = window.open(url, "_blank", "noopener,noreferrer");

    // Check if popup was blocked
    if (!newWindow || newWindow.closed || typeof newWindow.closed === "undefined") {
      // Fallback: copy to clipboard
      await navigator.clipboard.writeText(messageContent);
      return false; // Indicate fallback was used
    }

    return true; // Successfully opened
  } catch (error) {
    console.error("Failed to open Outlook draft:", error);

    // Fallback: try to copy to clipboard
    try {
      await navigator.clipboard.writeText(messageContent);
      return false;
    } catch (clipboardError) {
      console.error("Clipboard fallback also failed:", clipboardError);
      throw new Error("Could not open Outlook or copy to clipboard");
    }
  }
}
