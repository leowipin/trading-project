import type { InputFieldProps } from "./inputFieldProps";

const InputField = ({name, labelContent, ...rest}:InputFieldProps) => {

    return(
        <div className="flex flex-col">
            <label htmlFor={name}>{labelContent}</label>
            <input {...rest} name={name}
                className="rounded-sm"
            ></input>
        </div>
    )
}

export default InputField;