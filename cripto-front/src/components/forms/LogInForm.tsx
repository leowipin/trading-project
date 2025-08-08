import InputField from "./input-fields/InputField";
import type { LogInFormProps } from "./logInFormProps";
import BasicButton from "../buttons/BasicButton";

const LogInForm = ({...rest}:LogInFormProps) => {
    
    const logIn = async (formData:FormData):Promise<void> => {
        console.log(formData.get("email"))
        console.log(formData.get("password"))
    }

    return(
        <form
            action={logIn}
            {...rest}
            className="flex flex-col gap-4"
        >
            <InputField
                labelContent="Correo electrónico"
                name="email"
                type="text"
                id="email"
                autoComplete="email"
                required
            >
            </InputField>
            <InputField
                labelContent="Contraseña"
                name="password"
                type="password"
                id="password"
                autoComplete="current-password"
                required
            >
            </InputField>
            <BasicButton type="submit">Iniciar sesión</BasicButton>
        </form>
    )
}

export default LogInForm;