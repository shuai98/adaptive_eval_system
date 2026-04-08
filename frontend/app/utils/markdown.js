export function renderMarkdown(source = "") {
    const html = window.marked.parse(source || "", {
        breaks: true,
        gfm: true,
    });
    const template = document.createElement("template");
    template.innerHTML = html;

    template.content.querySelectorAll("pre").forEach((preElement) => {
        const codeElement = preElement.querySelector("code");
        if (!codeElement) return;

        try {
            window.hljs.highlightElement(codeElement);
        } catch (error) {
            console.warn("highlight_failed", error);
        }

        const wrapper = document.createElement("div");
        wrapper.className = "markdown-code-shell";

        const header = document.createElement("div");
        header.className = "markdown-code-header";

        const label = document.createElement("span");
        label.textContent = codeElement.className.replace("language-", "") || "代码";

        const button = document.createElement("button");
        button.type = "button";
        button.className = "markdown-copy-button";
        button.textContent = "复制";
        button.addEventListener("click", async () => {
            try {
                await navigator.clipboard.writeText(codeElement.textContent || "");
                button.textContent = "已复制";
                window.setTimeout(() => {
                    button.textContent = "复制";
                }, 1600);
            } catch (error) {
                console.warn("copy_failed", error);
                button.textContent = "复制失败";
                window.setTimeout(() => {
                    button.textContent = "复制";
                }, 1600);
            }
        });

        header.append(label, button);
        preElement.parentNode.insertBefore(wrapper, preElement);
        wrapper.append(header, preElement);
    });

    return template.innerHTML;
}
