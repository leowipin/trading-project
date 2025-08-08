import type { BasicButtonProps } from "./basicButtonProps"

const BasicButton = ({...rest}:BasicButtonProps) => {

    return(
        <button
            {...rest}
        >
        </button>
    )

}

export default BasicButton