import type { ReactNode } from "react";
import { exampleData } from "./exampleData";

interface DataButtonProps {
    function: string;
    disabled?: boolean;
    dataHandler?: (data: any) => void;
    children?: ReactNode;
    loading?: boolean;
}

export function DataButton(props: DataButtonProps) {

    let clickHandler: () => void = () => {};

    switch (props.function) {
        case "example":
            clickHandler = () => props.dataHandler?.(exampleData);
            break;
        case "paste":
            clickHandler = () => {
                const text = prompt("Paste your data here (JSON format):");
                if (text) {
                    try {
                        const data = JSON.parse(text);
                        props.dataHandler?.(data);
                    } catch (error) {
                        console.error("Invalid JSON format");
                        alert("Invalid JSON format. Please check your input and try again.");
                    }
                }
            }
            break;
        case "upload":
            clickHandler = () => {
                const input = document.createElement("input");
                input.type = "file";
                input.accept = ".json";
                input.onchange = (event) => {
                    const file = (event.target as HTMLInputElement).files?.[0];
                    if (file) {
                        const reader = new FileReader();
                        reader.onload = (e) => {
                            try {
                                const data = JSON.parse(e.target?.result as string);
                                props.dataHandler?.(data);
                            } catch (error) {
                                console.error("Invalid JSON format");
                                alert("Invalid JSON format. Please check your input and try again.");
                            }
                        };
                        reader.readAsText(file);
                    }
                };
                input.click();
            };
            break;
    }

    return (
        <button
            className="btn btn-primary mr-4 w-48"
            onClick={() => {
                clickHandler();
            }}
            disabled={props.disabled || props.loading}
        >
            {props.loading ? <span className="loading loading-spinner loading-md text-white"></span> : props.children}
        </button>
    );
}